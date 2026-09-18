"""
Blowdown Performance Evaluation — BS01 and BS02 sample data comparison.

Compares measured vs theoretical (simulated) pressure curves and generates
an Aker BP-branded HTML report with PASS/FAIL verdicts.
"""

import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

# Add skills to path
sys.path.insert(0, str(Path(__file__).parent / ".github/skills/blowdown-simulated-curves/scripts"))

from parse_simulated_curves import load_simulated_curves, fit_exponential, exp_decay

OSLO = ZoneInfo("Europe/Oslo")

# ============================================================================
# Configuration
# ============================================================================
FIELD = "Alvheim"
SEGMENTS = ["BS01", "BS02"]
INITIATION_TIME = datetime(2026, 6, 1, 10, 0, 0, tzinfo=OSLO)
ACCEPTANCE_CRITERION = 0.10  # ±10% max deviation from theoretical

SIMULATED_PATH = "raw/Alvheim Simulated Blowdown Curves.xlsx"
MEASURED_PATH = "raw/Alvheim Measured Example Data.xlsx"
OUTPUT_PATH = f"OutputDataFiles/{FIELD}_Blowdown_19Jun2026.html"

# ============================================================================
# Load simulated curves
# ============================================================================
print(f"Loading simulated curves from {SIMULATED_PATH}")
sim = load_simulated_curves(SIMULATED_PATH)
print(f"  Loaded {len(sim.segments)} simulated segments")

# ============================================================================
# Load measured data
# ============================================================================
print(f"\nLoading measured data from {MEASURED_PATH}")
df_raw = pd.read_excel(MEASURED_PATH, sheet_name="Measured Pressure", header=None)

# Parse the offset header structure
# Row 2: axis labels, Row 3: segment IDs (BS01, BS02), Row 4+: data
time_col = df_raw.iloc[4:, 0].dropna().astype(float).values
bs01_col = df_raw.iloc[4:, 1].dropna().astype(float).values
bs02_col = df_raw.iloc[4:, 2].dropna().astype(float).values

measured = {
    "BS01": {"time_s": time_col, "pressure": bs01_col},
    "BS02": {"time_s": time_col, "pressure": bs02_col},
}

for seg in SEGMENTS:
    print(f"  {seg}: {len(measured[seg]['time_s'])} points, "
          f"P0={measured[seg]['pressure'][0]:.2f} barg")

# ============================================================================
# Build theoretical comparison curves (anchored to measured P0)
# ============================================================================
print("\nBuilding theoretical comparison curves (anchored to measured P0)")
theoretical = {}

for seg in SEGMENTS:
    # Get the simulated decay constant k
    fit = fit_exponential(sim, seg)
    k_sim = fit["k"]
    tau_sim = fit["tau"]
    r2 = fit["r2"]
    
    # Measured initial pressure at t=0
    P0_measured = measured[seg]["pressure"][0]
    
    # Generate theoretical curve: P_theo(t) = P0_measured * exp(-k_sim * t)
    # Use the same time base as the measured data
    time_s = measured[seg]["time_s"]
    P_theo = exp_decay(time_s, P0_measured, k_sim)
    
    theoretical[seg] = {
        "time_s": time_s,
        "pressure": P_theo,
        "k": k_sim,
        "tau": tau_sim,
        "r2": r2,
        "P0_measured": P0_measured,
    }
    
    print(f"  {seg}: P0={P0_measured:.2f} barg, k={k_sim:.5f} 1/s, "
          f"tau={tau_sim:.1f} s (R²={r2:.4f})")

# ============================================================================
# Comparison and verdict
# ============================================================================
print("\nPerforming comparison")
results = {}

for seg in SEGMENTS:
    t_meas = measured[seg]["time_s"]
    P_meas = measured[seg]["pressure"]
    P_theo = theoretical[seg]["pressure"]
    
    # Compute percentage deviation at each time point
    # Only apply the percentage criterion where P_theo > 10% of P0 (main depressurisation zone)
    # Below that, the segment has essentially blown down and small absolute residuals are OK
    P0 = theoretical[seg]["P0_measured"]
    threshold = 0.10 * P0
    
    mask_main = P_theo > threshold
    if mask_main.sum() == 0:
        # Edge case: all points below threshold (shouldn't happen)
        deviation_pct = np.abs((P_meas - P_theo) / P_theo) * 100
        max_deviation_pct = deviation_pct.max()
        mean_deviation_pct = deviation_pct.mean()
    else:
        # Compute deviation only in the main depressurisation zone
        deviation_pct_main = np.abs((P_meas[mask_main] - P_theo[mask_main]) / P_theo[mask_main]) * 100
        max_deviation_pct = deviation_pct_main.max()
        mean_deviation_pct = deviation_pct_main.mean()
    
    # RMSE (over the full window)
    rmse = np.sqrt(np.mean((P_meas - P_theo)**2))
    
    # Time to 50% of P0
    P_target = 0.5 * P0
    
    # Theoretical time to 50%
    k = theoretical[seg]["k"]
    t_theo_50 = np.log(2) / k if k > 0 else np.inf
    
    # Measured time to 50% (linear interpolation)
    idx_below = np.where(P_meas <= P_target)[0]
    if len(idx_below) > 0:
        i = idx_below[0]
        if i > 0:
            t_meas_50 = np.interp(P_target, [P_meas[i], P_meas[i-1]], [t_meas[i], t_meas[i-1]])
        else:
            t_meas_50 = t_meas[0]
    else:
        t_meas_50 = None
    
    # Verdict: PASS if max deviation < 10%
    verdict = "PASS" if max_deviation_pct < (ACCEPTANCE_CRITERION * 100) else "FAIL"
    
    results[seg] = {
        "verdict": verdict,
        "max_deviation_pct": max_deviation_pct,
        "mean_deviation_pct": mean_deviation_pct,
        "rmse": rmse,
        "t_theo_50": t_theo_50,
        "t_meas_50": t_meas_50,
        "P0": P0,
        "k": k,
        "tau": theoretical[seg]["tau"],
    }
    
    print(f"  {seg}: {verdict}")
    print(f"    Max deviation: {max_deviation_pct:.1f}% (limit: {ACCEPTANCE_CRITERION*100}%)")
    print(f"    Mean deviation: {mean_deviation_pct:.1f}%")
    print(f"    RMSE: {rmse:.2f} barg")
    print(f"    t(50%): {t_theo_50:.1f} s theo, "
          f"{t_meas_50:.1f} s meas" if t_meas_50 else "not reached")

# ============================================================================
# Generate HTML report
# ============================================================================
print(f"\nGenerating HTML report: {OUTPUT_PATH}")

Path("OutputDataFiles").mkdir(exist_ok=True)

# Build Plotly chart JSON for each segment
chart_data = {}
for seg in SEGMENTS:
    t_meas = measured[seg]["time_s"]
    P_meas = measured[seg]["pressure"]
    P_theo = theoretical[seg]["pressure"]
    
    chart_data[seg] = {
        "theo_x": t_meas.tolist(),
        "theo_y": P_theo.tolist(),
        "meas_x": t_meas.tolist(),
        "meas_y": P_meas.tolist(),
        "P0": results[seg]["P0"],
    }

# HTML template
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{FIELD} Blowdown Performance — BS01 & BS02</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Lato', sans-serif;
            font-size: 15px;
            line-height: 1.6;
            color: #333;
            background: #fff;
            margin-left: 260px;
        }}
        .sidebar {{
            position: fixed;
            top: 0; left: 0; bottom: 0;
            width: 260px;
            background: linear-gradient(180deg, #7D2248 0%, #4a1429 100%);
            color: #fff;
            padding: 2rem 1.5rem;
            overflow-y: auto;
            z-index: 100;
        }}
        .sidebar-logo {{
            width: 120px;
            margin-bottom: 2rem;
            border-radius: 4px;
        }}
        .sidebar h2 {{
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            color: #fff;
        }}
        .sidebar nav {{
            margin-top: 2rem;
        }}
        .sidebar nav a {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.75rem 0;
            color: rgba(255,255,255,0.85);
            text-decoration: none;
            font-size: 0.95rem;
            transition: all 0.2s;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .sidebar nav a:hover {{
            color: #fff;
            padding-left: 0.5rem;
        }}
        .nav-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            flex-shrink: 0;
        }}
        .nav-dot.pass {{ background: #22c55e; }}
        .nav-dot.fail {{ background: #ef4444; }}
        .nav-dot.info {{ background: #CE0F69; }}
        .hero {{
            background: linear-gradient(135deg, #CE0F69 0%, #7D2248 100%);
            color: #fff;
            padding: 3rem 3rem 2rem;
            position: relative;
        }}
        .hero-content {{
            max-width: 1200px;
        }}
        .hero h1 {{
            font-size: 2.5rem;
            font-weight: 900;
            margin-bottom: 0.5rem;
            color: #fff;
        }}
        .hero-subtitle {{
            font-size: 1.1rem;
            opacity: 0.95;
            margin-bottom: 1rem;
        }}
        .badge {{
            display: inline-block;
            padding: 0.4rem 1rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge.pass {{ background: #22c55e; color: #fff; }}
        .badge.fail {{ background: #ef4444; color: #fff; }}
        .badge.mixed {{ background: #eab308; color: #000; }}
        main {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 3rem;
        }}
        section {{
            margin-bottom: 3rem;
        }}
        h2 {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #7D2248;
            margin-bottom: 1.5rem;
            border-bottom: 3px solid #CE0F69;
            padding-bottom: 0.5rem;
        }}
        h3 {{
            font-size: 1.3rem;
            font-weight: 700;
            color: #7D2248;
            margin: 2rem 0 1rem;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 2rem 0;
        }}
        .kpi-card {{
            background: #f1f1f1;
            border-radius: 8px;
            padding: 1.5rem;
            border-left: 4px solid #CE0F69;
        }}
        .kpi-card .label {{
            font-size: 0.85rem;
            color: #666;
            margin-bottom: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .kpi-card .value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #7D2248;
        }}
        .kpi-card .unit {{
            font-size: 0.95rem;
            color: #666;
            margin-left: 0.25rem;
        }}
        .callout {{
            padding: 1.25rem;
            border-radius: 6px;
            margin: 1.5rem 0;
            border-left: 4px solid;
        }}
        .callout.info {{
            background: rgba(206,15,105,0.08);
            border-color: #CE0F69;
            color: #4a1429;
        }}
        .callout.success {{
            background: rgba(34,197,94,0.1);
            border-color: #22c55e;
            color: #065f46;
        }}
        .callout.critical {{
            background: rgba(239,68,68,0.1);
            border-color: #ef4444;
            color: #991b1b;
        }}
        .chart-container {{
            margin: 2rem 0;
            background: #f9fafb;
            padding: 1.5rem;
            border-radius: 8px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            background: #fff;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        th {{
            background: #7D2248;
            color: #fff;
            padding: 1rem;
            text-align: left;
            font-weight: 700;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 0.5px;
        }}
        td {{
            padding: 0.85rem 1rem;
            border-bottom: 1px solid #e5e7eb;
        }}
        tr:nth-child(even) {{
            background: #f9fafb;
        }}
        tr:hover {{
            background: #f3f4f6;
        }}
        footer {{
            text-align: center;
            padding: 2rem;
            color: #666;
            border-top: 1px solid #e5e7eb;
            font-size: 0.9rem;
        }}
        footer strong {{
            color: #CE0F69;
        }}
    </style>
</head>
<body>
    <aside class="sidebar">
        <img src="https://companieslogo.com/img/orig/AKRBP.OL-c65af99e.png?t=1603469381" 
             alt="Aker BP" class="sidebar-logo">
        <h2>Blowdown Performance</h2>
        <nav>
            <a href="#overview"><span class="nav-dot info"></span> Overview</a>
            <a href="#bs01"><span class="nav-dot {results['BS01']['verdict'].lower()}"></span> BS01</a>
            <a href="#bs02"><span class="nav-dot {results['BS02']['verdict'].lower()}"></span> BS02</a>
            <a href="#summary"><span class="nav-dot info"></span> Summary</a>
        </nav>
    </aside>

    <header class="hero">
        <div class="hero-content">
            <h1>{FIELD} Blowdown Evaluation</h1>
            <p class="hero-subtitle">BS01 & BS02 • Measured vs Theoretical Comparison</p>
            <span class="badge {'pass' if all(r['verdict'] == 'PASS' for r in results.values()) else 'fail' if all(r['verdict'] == 'FAIL' for r in results.values()) else 'mixed'}">
                {'PASS' if all(r['verdict'] == 'PASS' for r in results.values()) else 'MIXED' if any(r['verdict'] == 'PASS' for r in results.values()) else 'FAIL'}
            </span>
        </div>
    </header>

    <main>
        <section id="overview">
            <h2>Overview</h2>
            <div class="callout info">
                <strong>Evaluation Methodology:</strong> Each segment's measured pressure curve is compared 
                against a theoretical comparison curve anchored to the measured starting pressure (P₀) 
                but using the simulated decay constant (k). Acceptance: maximum deviation must stay within 
                ±{ACCEPTANCE_CRITERION*100:.0f}% of the theoretical curve.
            </div>
            
            <h3>Event Details</h3>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="label">Initiation Time</div>
                    <div class="value" style="font-size:1.2rem;">{INITIATION_TIME.strftime('%Y-%m-%d %H:%M')}</div>
                </div>
                <div class="kpi-card">
                    <div class="label">Timezone</div>
                    <div class="value" style="font-size:1.2rem;">Europe/Oslo</div>
                </div>
                <div class="kpi-card">
                    <div class="label">Acceptance Criterion</div>
                    <div class="value">±{ACCEPTANCE_CRITERION*100:.0f}<span class="unit">%</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">Segments Evaluated</div>
                    <div class="value">{len(SEGMENTS)}</div>
                </div>
            </div>
        </section>
"""

# Add sections for each segment
for seg in SEGMENTS:
    r = results[seg]
    cd = chart_data[seg]
    
    verdict_class = r['verdict'].lower()
    verdict_color = '#22c55e' if verdict_class == 'pass' else '#ef4444'
    
    html += f"""
        <section id="{seg.lower()}">
            <h2>{seg}</h2>
            
            <div class="callout {verdict_class if verdict_class != 'fail' else 'critical'}">
                <strong>Verdict: {r['verdict']}</strong> &mdash; 
                {seg} depressurised with a maximum deviation of <strong>{r['max_deviation_pct']:.1f}%</strong> from 
                the theoretical curve (mean {r['mean_deviation_pct']:.1f}%, RMSE {r['rmse']:.2f} barg). 
                {'Within' if r['verdict'] == 'PASS' else 'Exceeds'} the ±{ACCEPTANCE_CRITERION*100:.0f}% acceptance limit.
            </div>
            
            <h3>Key Performance Indicators</h3>
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="label">Starting Pressure (P₀)</div>
                    <div class="value">{r['P0']:.1f}<span class="unit">barg</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">Decay Constant (k)</div>
                    <div class="value">{r['k']:.5f}<span class="unit">1/s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">Time Constant (τ)</div>
                    <div class="value">{r['tau']:.1f}<span class="unit">s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">Max Deviation</div>
                    <div class="value" style="color:{verdict_color};">{r['max_deviation_pct']:.1f}<span class="unit">%</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">Mean Deviation</div>
                    <div class="value">{r['mean_deviation_pct']:.1f}<span class="unit">%</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">RMSE</div>
                    <div class="value">{r['rmse']:.2f}<span class="unit">barg</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">t(50%) Theoretical</div>
                    <div class="value">{r['t_theo_50']:.1f}<span class="unit">s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="label">t(50%) Measured</div>
                    <div class="value">{f"{r['t_meas_50']:.1f}" if r['t_meas_50'] else "—"}<span class="unit">{' s' if r['t_meas_50'] else ''}</span></div>
                </div>
            </div>
            
            <h3>Pressure vs Time</h3>
            <div class="chart-container">
                <div id="chart-{seg.lower()}" style="width:100%;height:500px;"></div>
            </div>
        </section>
    """

# Summary table
html += f"""
        <section id="summary">
            <h2>Summary</h2>
            <table>
                <thead>
                    <tr>
                        <th>Segment</th>
                        <th>P₀ [barg]</th>
                        <th>k [1/s]</th>
                        <th>Max Dev [%]</th>
                        <th>Mean Dev [%]</th>
                        <th>RMSE [barg]</th>
                        <th>Verdict</th>
                    </tr>
                </thead>
                <tbody>
"""

for seg in SEGMENTS:
    r = results[seg]
    verdict_badge = f'<span class="badge {r["verdict"].lower()}">{r["verdict"]}</span>'
    html += f"""
                    <tr>
                        <td><strong>{seg}</strong></td>
                        <td>{r['P0']:.1f}</td>
                        <td>{r['k']:.5f}</td>
                        <td>{r['max_deviation_pct']:.1f}</td>
                        <td>{r['mean_deviation_pct']:.1f}</td>
                        <td>{r['rmse']:.2f}</td>
                        <td>{verdict_badge}</td>
                    </tr>
"""

html += """
                </tbody>
            </table>
        </section>
    </main>

    <footer>
        <strong>PE Assistant</strong> &bull; Blowdown Performance Evaluator &bull; 
        19 June 2026 &bull; Norway time (CEST)
    </footer>

    <script>
        // Lazy-load Plotly charts
        const chartConfigs = {
"""

for seg in SEGMENTS:
    cd = chart_data[seg]
    html += f"""
            '{seg.lower()}': {{
                data: [
                    {{
                        x: {cd['theo_x']},
                        y: {cd['theo_y']},
                        mode: 'lines',
                        name: 'Theoretical (k<sub>sim</sub>, P₀<sub>meas</sub>)',
                        line: {{ color: '#CE0F69', width: 3 }}
                    }},
                    {{
                        x: {cd['meas_x']},
                        y: {cd['meas_y']},
                        mode: 'lines',
                        name: 'Measured',
                        line: {{ color: '#7D2248', width: 2, dash: 'dot' }}
                    }},
                    {{
                        x: [0],
                        y: [{cd['P0']}],
                        mode: 'markers',
                        name: 'P₀ (measured)',
                        marker: {{ color: '#22c55e', size: 10, symbol: 'circle' }}
                    }}
                ],
                layout: {{
                    xaxis: {{ title: 'Time [s]', gridcolor: '#e5e7eb' }},
                    yaxis: {{ title: 'Pressure [barg]', gridcolor: '#e5e7eb' }},
                    plot_bgcolor: '#fff',
                    paper_bgcolor: '#f9fafb',
                    font: {{ family: 'Lato, sans-serif' }},
                    legend: {{ x: 0.7, y: 0.95 }},
                    margin: {{ l: 60, r: 30, t: 30, b: 60 }}
                }}
            }},
"""

html += """
        };

        // IntersectionObserver for lazy loading
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chartId = entry.target.id;
                    const segKey = chartId.replace('chart-', '');
                    if (chartConfigs[segKey]) {
                        Plotly.newPlot(chartId, chartConfigs[segKey].data, chartConfigs[segKey].layout, 
                                       {responsive: true, displayModeBar: false});
                        observer.unobserve(entry.target);
                    }
                }
            });
        }, { threshold: 0.1 });

        // Observe all chart containers
        document.querySelectorAll('.chart-container > div[id^="chart-"]').forEach(el => {
            observer.observe(el);
        });
    </script>
</body>
</html>
"""

# Write to file
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"✓ Report saved: {OUTPUT_PATH}")
print(f"\nVerdicts: {', '.join(f'{s}={results[s]['verdict']}' for s in SEGMENTS)}")
