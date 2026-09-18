#!/usr/bin/env python3
"""
Consolidated Blowdown Performance Evaluator

Evaluates topside blowdown segment performance against simulated curves.
Runs the entire pipeline: load simulated curves, retrieve measured data,
perform evaluation, and generate HTML report.

Usage:
    python evaluate_blowdown_consolidated.py \
        --field Alvheim \
        --segments BS01,BS02 \
        --start "2026-01-11T17:51:06" \
        --criterion "10% P0" \
        --tags BS01=ALV_16PST0139/MeasA/PRIM,BS02=ALV_16PST0239/MeasA/PRIM \
        --output-dir OutputDataFiles

    # Or use example data instead of CDF:
    python evaluate_blowdown_consolidated.py \
        --field Alvheim \
        --segments BS01,BS02 \
        --start "2026-01-11T17:51:06" \
        --use-example-data \
        --output-dir OutputDataFiles
"""

import argparse
import json
import pickle
import sys
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Add skill scripts to path
sys.path.insert(0, str(Path(__file__).parent / ".github/skills/blowdown-simulated-curves/scripts"))
sys.path.insert(0, str(Path(__file__).parent / ".github/skills/blowdown-measured-curves/scripts"))

from parse_simulated_curves import load_simulated_curves, fit_exponential, exp_decay


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate blowdown segment performance")
    parser.add_argument("--field", required=True, help="Field name (e.g., Alvheim, Skarv)")
    parser.add_argument("--segments", required=True, help="Comma-separated segment IDs (e.g., BS01,BS02)")
    parser.add_argument("--start", required=True, help="Blowdown start time (Europe/Oslo), e.g., '2026-01-11T17:51:06'")
    parser.add_argument("--end", help="Blowdown end time (Europe/Oslo). Defaults to start + 30 minutes")
    parser.add_argument("--criterion", default="10% P0", help="Acceptance criterion (default: '10%% P0')")
    parser.add_argument("--tags", help="Segment to external_id mapping: BS01=tag1|tag2,BS02=tag3")
    parser.add_argument("--use-example-data", action="store_true", help="Use example measured data instead of CDF")
    parser.add_argument("--output-dir", default="OutputDataFiles", help="Output directory for HTML report")
    parser.add_argument("--no-cache", action="store_true", help="Disable simulated curves caching")
    return parser.parse_args()


def load_measured_from_example(field: str, segments: list) -> dict:
    """Load measured data from example Excel file."""
    example_file = Path(f"raw/{field} Measured Example Data.xlsx")
    if not example_file.exists():
        raise FileNotFoundError(f"Example data file not found: {example_file}")
    
    df = pd.read_excel(example_file, sheet_name='Measured Pressure')
    
    # Find header row
    header_row_idx = None
    for i in range(len(df)):
        row = df.iloc[i].astype(str)
        if 'BS01' in row.values or 'BS02' in row.values:
            header_row_idx = i
            break
    
    if header_row_idx is None:
        raise ValueError("Could not find segment ID header row in example data")
    
    # Parse data
    data_start = header_row_idx + 1
    data = df.iloc[data_start:].reset_index(drop=True)
    
    time_s = pd.to_numeric(data.iloc[:, 0], errors='coerce').dropna().values
    
    result = {'time_s': time_s}
    
    # Map columns to segments
    header = df.iloc[header_row_idx]
    for i, seg in enumerate(segments):
        # Find column index for this segment
        col_idx = None
        for j, val in enumerate(header):
            if str(val).strip() == seg:
                col_idx = j
                break
        
        if col_idx is not None:
            pressure = pd.to_numeric(data.iloc[:len(time_s), col_idx], errors='coerce').values
            result[seg] = pressure
    
    return result


def load_measured_from_cdf(tags: dict, start_time, end_time) -> dict:
    """Load measured data from CDF."""
    from retrieve_measured_curves import cdf_interactive_client, retrieve_measured_curve
    
    print("Connecting to CDF (browser login)...")
    client = cdf_interactive_client()
    
    print(f"Retrieving measured curves from {start_time} to {end_time}...")
    result = {}
    for seg, external_ids in tags.items():
        candidates = external_ids if isinstance(external_ids, list) else [external_ids]
        curves = []
        for external_id in candidates:
            try:
                curve = retrieve_measured_curve(
                    client, external_id, start_time, end_time,
                    segment=seg, t0=start_time,
                )
                curves.append((float(curve.pressure[0]), external_id, curve))
            except Exception as exc:
                print(f"  ! {seg} ({external_id}): {exc}")
        if curves:
            initial_pressure, external_id, curve = max(curves, key=lambda item: item[0])
            print(f"  {seg}: selected {external_id} (P0={initial_pressure:.3f} barg)")
            result[seg] = {
                'time_s': curve.time_s,
                'pressure': curve.pressure,
                'external_id': external_id,
            }
    
    return result


def load_tag_mapping(field: str, segments: list) -> tuple[dict, dict]:
    """Load segment tags and optional names from the asset mapping workbook."""
    candidates = [
        Path(f"raw/{field} Pressure Measurement Tags.xlsx"),
        Path(f"raw/{field} Pressure Measurement External IDs.xlsx"),
    ]
    tag_file = next((path for path in candidates if path.exists()), None)
    if tag_file is None:
        raise FileNotFoundError(
            f"Tag mapping file not found; checked: {', '.join(str(p) for p in candidates)}"
        )

    tag_df = pd.read_excel(tag_file, header=None)
    tags = {}
    names = {}
    for _, row in tag_df.iterrows():
        seg = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        if seg not in segments:
            continue
        tag_value = row.iloc[1] if len(row) > 1 else None
        if pd.notna(tag_value):
            tag_values = [value.strip() for value in str(tag_value).split(' and ') if value.strip()]
            tags[seg] = tag_values if len(tag_values) > 1 else tag_values[0]
        if len(row) > 2 and pd.notna(row.iloc[2]) and str(row.iloc[2]).strip():
            names[seg] = str(row.iloc[2]).strip()
    return tags, names


def evaluate_segment(segment_id: str, external_id: str, measured_pressure: np.ndarray,
                     time_s: np.ndarray, sim_fit: dict, P0_measured: float,
                     band_width: float) -> dict:
    """Evaluate a single segment."""

    if P0_measured < 3.0:
        return {
            'segment': segment_id,
            'external_id': external_id,
            'measured': measured_pressure,
            'theoretical': exp_decay(time_s, P0_measured, sim_fit['k']),
            'time_s': time_s,
            'P0': P0_measured,
            'k': sim_fit['k'],
            'tau': sim_fit['tau'],
            'r2': sim_fit['r2'],
            'band_width': band_width,
            'upper_limit': np.full_like(time_s, np.nan),
            'lower_limit': np.full_like(time_s, np.nan),
            'rmse': float('nan'),
            'max_dev': float('nan'),
            'max_percent_of_p0': float('nan'),
            'pass': False,
            'status': 'ALREADY DEPRESSURISED',
            't_50_theo': None,
            't_50_meas': None,
        }
    
    # Build theoretical comparison curve
    theo_curve = exp_decay(time_s, P0_measured, sim_fit['k'])
    
    # Acceptance bands
    upper_limit = theo_curve + band_width
    lower_limit = theo_curve - band_width
    
    # Deviation metrics
    deviation = measured_pressure - theo_curve
    rmse = np.sqrt(np.mean(deviation**2))
    max_dev = np.max(np.abs(deviation))
    max_percent_of_p0 = (max_dev / abs(P0_measured)) * 100 if P0_measured else float('nan')
    
    # Pass/review status
    within_band = (measured_pressure >= lower_limit) & (measured_pressure <= upper_limit)
    passed = np.all(within_band)
    
    # Time to 50%
    def time_to_pressure(t, p, target):
        idx = np.where(p <= target)[0]
        return t[idx[0]] if len(idx) > 0 else None
    
    t_50_theo = time_to_pressure(time_s, theo_curve, 0.5 * P0_measured)
    t_50_meas = time_to_pressure(time_s, measured_pressure, 0.5 * P0_measured)
    
    return {
        'segment': segment_id,
        'external_id': external_id,
        'measured': measured_pressure,
        'theoretical': theo_curve,
        'time_s': time_s,
        'P0': P0_measured,
        'k': sim_fit['k'],
        'tau': sim_fit['tau'],
        'r2': sim_fit['r2'],
        'band_width': band_width,
        'upper_limit': upper_limit,
        'lower_limit': lower_limit,
        'rmse': rmse,
        'max_dev': max_dev,
        'max_percent_of_p0': max_percent_of_p0,
        'pass': passed,
        'status': 'PASS' if passed else 'REVIEW',
        't_50_theo': t_50_theo,
        't_50_meas': t_50_meas,
    }


def generate_html_report(field: str, event_date: str, event_timestamp: str, results: dict, output_dir: str):
    """Generate full Aker BP-branded HTML report with Plotly charts."""
    
    segments_data = results['segments']
    
    # Count pass/review
    n_review = sum(1 for seg in segments_data.values() if seg['status'] == 'REVIEW')
    n_pass = sum(1 for seg in segments_data.values() if seg['status'] == 'PASS')
    n_already = sum(1 for seg in segments_data.values() if seg['status'] == 'ALREADY DEPRESSURISED')
    
    badge_class = "badge-fail" if n_review > 0 else "badge-pass"
    badge_text = f"{n_review} SEGMENT{'S' if n_review != 1 else ''} REVIEW" if n_review > 0 else "ALL SEGMENTS PASS"

    def segment_label(seg_id: str, seg_data: dict) -> str:
        name = seg_data.get('segment_name', '').strip()
        return f"{seg_id} — {name}" if name else seg_id

    
    # Platform images
    platform_images = {
        'Alvheim': 'https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/08-alvheim4x.png?ssl=1',
        'Skarv': 'https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/07-skarv4x.png?ssl=1',
        'Edvard Grieg': 'https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/10-edvard-grieg4x.png?ssl=1',
        'Ivar Aasen': 'https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/09-ivar-aasen4x.png?ssl=1',
        'Valhall': 'https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/13-valhall4x-3.png?ssl=1',
    }
    platform_img = platform_images.get(field, '')
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{field} Blowdown Evaluation - {event_timestamp}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.20.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Lato', sans-serif; background: #fff; color: #333; display: flex; min-height: 100vh; }}
        .sidebar {{ width: 260px; background: #2d2d2d; color: #fff; position: fixed; height: 100vh; overflow-y: auto; padding: 30px 20px; }}
        .sidebar-logo {{ width: 120px; margin-bottom: 30px; }}
        .sidebar h2 {{ font-size: 18px; font-weight: 700; margin-bottom: 25px; color: #CE0F69; }}
        .sidebar nav a {{ display: flex; align-items: center; color: #e0e0e0; text-decoration: none; padding: 10px 0; font-size: 14px; transition: color 0.2s; }}
        .sidebar nav a:hover {{ color: #CE0F69; }}
        .nav-dot {{ width: 8px; height: 8px; border-radius: 50%; margin-right: 10px; }}
        .dot-fail {{ background: #ef4444; }}
        .dot-pass {{ background: #22c55e; }}
        .dot-info {{ background: #3b82f6; }}
        .main-content {{ margin-left: 260px; flex: 1; width: calc(100% - 260px); }}
        .hero {{ background: linear-gradient(135deg, #CE0F69 0%, #7D2248 100%); color: #fff; padding: 60px 50px; position: relative; }}
        .hero h1 {{ font-size: 32px; font-weight: 900; margin-bottom: 15px; }}
        .hero .subtitle {{ font-size: 16px; font-weight: 300; opacity: 0.95; }}
        .badge {{ display: inline-block; padding: 6px 16px; border-radius: 20px; font-size: 13px; font-weight: 700; margin-top: 15px; }}
        .badge-fail {{ background: #ef4444; color: #fff; }}
        .badge-pass {{ background: #22c55e; color: #fff; }}
        .badge-already {{ background: #b7e4c7; color: #1b4332; }}
        .platform-thumb {{ position: absolute; right: 50px; top: 50%; transform: translateY(-50%); width: 200px; height: auto; opacity: 0.3; }}
        .content-section {{ padding: 50px; }}
        .content-section h2 {{ color: #7D2248; font-size: 26px; font-weight: 700; margin-bottom: 25px; }}
        .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
        .kpi-card {{ background: #f1f1f1; border-radius: 8px; padding: 20px; }}
        .kpi-label {{ font-size: 13px; color: #666; font-weight: 400; margin-bottom: 8px; }}
        .kpi-value {{ font-size: 28px; font-weight: 700; color: #CE0F69; }}
        .kpi-unit {{ font-size: 16px; color: #666; font-weight: 400; }}
        .callout {{ border-left: 4px solid; padding: 15px 20px; margin: 20px 0; border-radius: 4px; }}
        .callout-critical {{ background: #fef2f2; border-color: #ef4444; }}
        .callout-warning {{ background: #fffbeb; border-color: #9a8300; }}
        .callout-info {{ background: #eff6ff; border-color: #3b82f6; }}
        .callout-success {{ background: #f0fdf4; border-color: #008a59; }}
        .callout-already {{ background: #e9f7ef; border-color: #74c69d; }}
        .callout-title {{ font-weight: 700; margin-bottom: 8px; font-size: 14px; }}
        .callout-critical .callout-title {{ color: #ef4444; }}
        .callout-warning .callout-title {{ color: #9a8300; }}
        .callout-info .callout-title {{ color: #3b82f6; }}
        .callout-success .callout-title {{ color: #008a59; }}
        .chart-container {{ width: 100%; height: 500px; margin: 30px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        thead {{ background: #CE0F69; color: #fff; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e5e5e5; }}
        tbody tr:nth-child(even) {{ background: #f9f9f9; }}
        tbody tr:hover {{ background: #f1f1f1; }}
        .footer {{ background: #2d2d2d; color: #ccc; text-align: center; padding: 30px; font-size: 13px; }}
        .footer strong {{ color: #CE0F69; }}
    </style>
</head>
<body>
    <aside class="sidebar">
        <img src="https://companieslogo.com/img/orig/AKRBP.OL-c65af99e.png?t=1603469381" alt="Aker BP" class="sidebar-logo">
        <h2>Blowdown Evaluation</h2>
        <nav>
            <a href="#overview"><span class="nav-dot dot-info"></span>Overview</a>
"""
    
    # Add segment nav links
    for seg_id, seg_data in segments_data.items():
        dot_class = "dot-pass" if seg_data['status'] in ('PASS', 'ALREADY DEPRESSURISED') else "dot-fail"
        html += f'            <a href="#{seg_id}"><span class="nav-dot {dot_class}"></span>{html_escape(segment_label(seg_id, seg_data))}</a>\n'
    
    html += f"""            <a href="#summary"><span class="nav-dot dot-info"></span>Summary</a>
        </nav>
    </aside>
    
    <main class="main-content">
        <div class="hero">
            <h1>{field} Blowdown Performance Evaluation</h1>
            <p class="subtitle">Segments {', '.join(html_escape(segment_label(seg_id, data)) for seg_id, data in segments_data.items())} • Blowdown initiation: {event_timestamp}</p>
            <span class="badge {badge_class}">{badge_text}</span>
            <img src="{platform_img}" alt="{field}" class="platform-thumb">
        </div>
        
        <section id="overview" class="content-section">
            <h2>Overview</h2>
            <p style="margin-bottom: 20px;">
                This report evaluates the blowdown performance of segments <strong>{', '.join(html_escape(segment_label(seg_id, data)) for seg_id, data in segments_data.items())}</strong> 
                on {field} against simulated depressurisation curves, from a blowdown initiated at <strong>{event_timestamp}</strong> (t = 0). 
                The acceptance criterion is <strong>±10% of each segment's own starting pressure (P0) around the theoretical curve</strong> 
                (the measured curve must stay within the green bands throughout; the band width in barg is segment-specific).
            </p>
            
            <table>
                <thead>
                    <tr>
                        <th>Segment</th>
                        <th>Tag Number</th>
                        <th>P0 [barg]</th>
                        <th>Time to 50% (Meas)</th>
                        <th>Time to 50% (Theo)</th>
                        <th>Deviation</th>
                        <th>Max % Dev</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
    
    # Add table rows
    for seg_id, seg_data in segments_data.items():
        status_badge = "badge-already" if seg_data['status'] == 'ALREADY DEPRESSURISED' else "badge-pass" if seg_data['pass'] else "badge-fail"
        status_text = seg_data['status']
        
        # Handle None values for time-to-50%
        t_50_meas_str = f"{seg_data['t_50_meas']:.1f} s" if seg_data['t_50_meas'] is not None else "N/A"
        t_50_theo_str = f"{seg_data['t_50_theo']:.1f} s" if seg_data['t_50_theo'] is not None else "N/A"
        t_50_delta_str = f"{seg_data['t_50_meas'] - seg_data['t_50_theo']:.1f} s" if (seg_data['t_50_meas'] is not None and seg_data['t_50_theo'] is not None) else "N/A"
        
        html += f"""                    <tr>
                        <td><strong>{html_escape(segment_label(seg_id, seg_data))}</strong></td>
                        <td><code style="font-size: 11px; background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{seg_data['external_id']}</code></td>
                        <td>{seg_data['P0']:.2f}</td>
                        <td>{t_50_meas_str}</td>
                        <td>{t_50_theo_str}</td>
                        <td>{t_50_delta_str}</td>
                        <td>{seg_data['max_percent_of_p0']:.1f}%</td>
                        <td><span class="badge {status_badge}">{status_text}</span></td>
                    </tr>
"""
    
    html += """                </tbody>
            </table>
        </section>
"""
    
    # Add segment sections
    for seg_id, seg_data in segments_data.items():
        status_class = "success" if seg_data['status'] == 'PASS' else "already" if seg_data['status'] == 'ALREADY DEPRESSURISED' else "critical"
        status_text = seg_data['status']
        
        # Build summary text handling None values
        if seg_data['t_50_meas'] is not None and seg_data['t_50_theo'] is not None:
            timing_text = f"{html_escape(segment_label(seg_id, seg_data))} reached 50% of its starting pressure ({seg_data['P0']/2:.2f} barg) in <strong>{seg_data['t_50_meas']:.1f} seconds</strong>, which is <strong>{abs(seg_data['t_50_theo'] - seg_data['t_50_meas']):.1f} seconds {'faster' if seg_data['t_50_meas'] < seg_data['t_50_theo'] else 'slower'}</strong> than the theoretical comparison curve predicts ({seg_data['t_50_theo']:.1f} s)."
        elif seg_data['t_50_meas'] is not None:
            timing_text = f"{html_escape(segment_label(seg_id, seg_data))} reached 50% of its starting pressure ({seg_data['P0']/2:.2f} barg) in <strong>{seg_data['t_50_meas']:.1f} seconds</strong>."
        else:
            timing_text = f"{html_escape(segment_label(seg_id, seg_data))} did not reach 50% pressure within the observation window."

        if seg_data['status'] == 'ALREADY DEPRESSURISED':
            timing_text = f"{html_escape(segment_label(seg_id, seg_data))} started below 3 barg and is classified as already depressurised."
        
        html += f"""        
        <section id="{seg_id}" class="content-section">
            <h2>{html_escape(segment_label(seg_id, seg_data))} Analysis</h2>
            <p style="margin-bottom: 20px; color: #666;"><strong>Tag:</strong> <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-size: 13px;">{seg_data['external_id']}</code></p>
            
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">Starting Pressure</div>
                    <div class="kpi-value">{seg_data['P0']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Decay Constant (k)</div>
                    <div class="kpi-value">{seg_data['k']:.6f} <span class="kpi-unit">/s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Time Constant (tau)</div>
                    <div class="kpi-value">{seg_data['tau']:.1f} <span class="kpi-unit">s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">RMSE</div>
                    <div class="kpi-value">{seg_data['rmse']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
            </div>
            
            <div id="chart-{seg_id}" class="chart-container"></div>
            
            <div class="callout callout-{status_class}">
                <div class="callout-title">{html_escape(segment_label(seg_id, seg_data))} — {status_text}</div>
                {timing_text}
                {f"Maximum deviation of <strong>{seg_data['max_dev']:.2f} barg ({seg_data['max_percent_of_p0']:.1f}% of P0)</strong> {'is within' if seg_data['pass'] else 'exceeds'} the ±{seg_data['band_width']:.2f} barg (10% of P0) criterion." if seg_data['status'] != 'ALREADY DEPRESSURISED' else 'The normal curve-deviation criterion is not applied.'}
            </div>
        </section>
"""
    
    # Summary section
    html += f"""        
        <section id="summary" class="content-section">
            <h2>Summary</h2>
            
            <div class="callout callout-{'success' if n_review == 0 else 'warning'}">
                <div class="callout-title">Key Findings</div>
                <ul style="margin-left: 20px; line-height: 1.8;">
                    <li><strong>{n_pass} segment{'s' if n_pass != 1 else ''} PASS</strong>, <strong>{n_review} segment{'s' if n_review != 1 else ''} REVIEW</strong>, <strong>{n_already} already depressurised</strong> (P0 &lt; 3 barg)</li>
"""
    
    for seg_id, seg_data in segments_data.items():
        summary_text = (f"Starting pressure below 3 barg — <strong>ALREADY DEPRESSURISED</strong>"
                if seg_data['status'] == 'ALREADY DEPRESSURISED' else
                f"Maximum deviation = {seg_data['max_dev']:.2f} barg ({seg_data['max_percent_of_p0']:.1f}% of P0) — <strong>{seg_data['status']}</strong>")
        html += f"""                    <li>{html_escape(segment_label(seg_id, seg_data))}: {summary_text}</li>
"""
    
    html += """                </ul>
            </div>
        </section>
        
        <footer class="footer">
            <strong>Blowdown Buddy</strong> • Blowdown Performance Evaluator • 
            """ + datetime.now().strftime("%d %B %Y") + """ • Norway time (CEST)
        </footer>
    </main>
    
    <script>
"""
    
    # Add Plotly charts
    for chart_index, (seg_id, seg_data) in enumerate(segments_data.items()):
        chart_key = f"segment_{chart_index}"
        time_s = seg_data['time_s']
        html += f"""
var trace_meas_{chart_key} = {{
    x: {json.dumps(time_s.tolist())},
    y: {json.dumps(seg_data['measured'].tolist())},
    mode: 'lines',
    name: 'Measured',
    line: {{color: '#ef4444', width: 2}}
}};

var trace_theo_{chart_key} = {{
    x: {json.dumps(time_s.tolist())},
    y: {json.dumps(seg_data['theoretical'].tolist())},
    mode: 'lines',
    name: 'Theoretical',
    line: {{color: '#3b82f6', width: 2, dash: 'dash'}}
}};

var trace_upper_{chart_key} = {{
    x: {json.dumps(time_s.tolist())},
    y: {json.dumps(seg_data['upper_limit'].tolist())},
    mode: 'lines',
    name: 'Upper limit (+10% P0)',
    line: {{color: '#22c55e', width: 1, dash: 'dot'}}
}};

var trace_lower_{chart_key} = {{
    x: {json.dumps(time_s.tolist())},
    y: {json.dumps(seg_data['lower_limit'].tolist())},
    mode: 'lines',
    name: 'Lower limit (-10% P0)',
    line: {{color: '#22c55e', width: 1, dash: 'dot'}}
}};

var layout_{chart_key} = {{
    title: {json.dumps(segment_label(seg_id, seg_data) + ' — Measured vs Theoretical')},
    xaxis: {{ title: 'Time [s]', gridcolor: '#e5e5e5' }},
    yaxis: {{ title: 'Pressure [barg]', gridcolor: '#e5e5e5' }},
    plot_bgcolor: '#fafafa',
    paper_bgcolor: '#fff',
    font: {{family: 'Lato, sans-serif'}},
    legend: {{x: 0.7, y: 0.95}},
    hovermode: 'x unified'
}};

Plotly.newPlot('chart-{seg_id}', [trace_meas_{chart_key}, trace_theo_{chart_key}, trace_upper_{chart_key}, trace_lower_{chart_key}], layout_{chart_key}, {{responsive: true}});
"""
    
    html += """    </script>
</body>
</html>"""
    
    # Save report
    output_path = Path(output_dir) / f"{field}_Blowdown_{event_date.replace(' ', '_')}.html"
    output_path.parent.mkdir(exist_ok=True, parents=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\nHTML report generated: {output_path}")
    return output_path


def main():
    args = parse_args()
    
    # Parse inputs
    field = args.field
    segments = [s.strip() for s in args.segments.split(',')]
    start_time = pd.Timestamp(args.start, tz=ZoneInfo("Europe/Oslo"))
    
    if args.end:
        end_time = pd.Timestamp(args.end, tz=ZoneInfo("Europe/Oslo"))
    else:
        end_time = start_time + pd.Timedelta(minutes=30)
    
    # Parse tags if provided
    tags = {}
    segment_names = {}
    if args.tags:
        for pair in args.tags.split(','):
            seg, tag = pair.split('=')
            tag_values = [value.strip() for value in tag.split('|') if value.strip()]
            tags[seg.strip()] = tag_values if len(tag_values) > 1 else tag_values[0]

    # Load names from the asset mapping workbook even when tags are supplied on
    # the command line, so report labels remain complete.
    if not args.use_example_data:
        try:
            mapped_tags, segment_names = load_tag_mapping(field, segments)
            for seg, tag in mapped_tags.items():
                tags.setdefault(seg, tag)
            print(f"  Loaded segment names from the {field} pressure-tag mapping")
        except FileNotFoundError as exc:
            if not tags:
                print(f"  Error: {exc}")
                return 1
    
    # Load simulated curves
    print(f"Loading simulated curves for {field}...")
    sim_file = Path(f"raw/{field} Simulated Blowdown Curves.xlsx")
    if not sim_file.exists():
        print(f"Error: Simulated curves file not found: {sim_file}")
        return 1
    
    sim_res = load_simulated_curves(str(sim_file), use_cache=not args.no_cache)
    print(f"  Loaded {len(sim_res.segments)} simulated segments")
    
    # Fit exponential models
    print("Fitting exponential decay models...")
    sim_fits = {}
    for seg in segments:
        if seg not in sim_res.segments:
            print(f"  Warning: {seg} not in simulated segments, skipping")
            continue
        sim_fits[seg] = fit_exponential(sim_res, seg)
        print(f"  {seg}: k={sim_fits[seg]['k']:.6f} /s, tau={sim_fits[seg]['tau']:.1f} s, R2={sim_fits[seg]['r2']:.4f}")
    
    # Load measured data
    print("\nLoading measured data...")
    if args.use_example_data:
        measured = load_measured_from_example(field, segments)
    else:
        if not tags:
            print("Error: No external IDs found for the requested segments")
            return 1
        measured = load_measured_from_cdf(tags, start_time, end_time)
    
    # Get max time length for reporting
    max_time = max(seg_data['time_s'][-1] for seg_data in measured.values())
    print(f"  Retrieved data over {max_time:.1f} seconds")
    
    # Evaluate segments
    print("\nEvaluating segments...")
    results = {
        'segments': {}
    }
    
    for seg in segments:
        if seg not in measured or seg not in sim_fits:
            print(f"  Skipping {seg} (missing data)")
            continue
        
        if seg not in tags:
            print(f"  Error: No external ID found for {seg}")
            continue
        
        seg_data = measured[seg]
        time_s = seg_data['time_s']
        pressure = seg_data['pressure']
        
        P0 = pressure[0]
        band_width = 0.10 * abs(P0)  # +/- 10% of the starting-pressure magnitude
        external_id = seg_data.get('external_id', tags[seg])
        
        seg_result = evaluate_segment(
            seg, external_id, pressure, time_s, 
            sim_fits[seg], P0, band_width
        )
        seg_result['segment_name'] = segment_names.get(seg, '')
        
        results['segments'][seg] = seg_result
        
        status = seg_result['status']
        if status == 'ALREADY DEPRESSURISED':
            print(f"  {seg}: {status} (P0 = {P0:.3f} barg)")
        else:
            print(f"  {seg}: {status} (max dev = {seg_result['max_dev']:.2f} barg, {seg_result['max_percent_of_p0']:.1f}% of P0)")
    
    # Generate HTML report
    event_date = start_time.strftime("%d %b %Y")
    event_timestamp = start_time.strftime("%d %b %Y, %H:%M:%S") + " (Europe/Oslo)"
    generate_html_report(field, event_date, event_timestamp, results, args.output_dir)
    
    # Summary
    n_review = sum(1 for seg in results['segments'].values() if seg['status'] == 'REVIEW')
    n_pass = sum(1 for seg in results['segments'].values() if seg['status'] == 'PASS')
    n_already = sum(1 for seg in results['segments'].values() if seg['status'] == 'ALREADY DEPRESSURISED')
    
    print(f"\n{'='*60}")
    print(f"Evaluation Complete: {n_pass} PASS, {n_review} REVIEW, {n_already} ALREADY DEPRESSURISED")
    print(f"{'='*60}")
    
    return 0 if n_review == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
