import pickle
import json
from datetime import datetime

# Load evaluation results
with open('evaluation_results.pkl', 'rb') as f:
    results = pickle.load(f)

time_s = results['time_s']
bs01 = results['segments']['BS01']
bs02 = results['segments']['BS02']

# Create HTML report
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alvheim Blowdown Evaluation - BS01 & BS02</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">
    <script src="https://cdn.plot.ly/plotly-2.20.0.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Lato', sans-serif;
            background: #fff;
            color: #333;
            display: flex;
            min-height: 100vh;
        }}
        
        .sidebar {{
            width: 260px;
            background: #2d2d2d;
            color: #fff;
            position: fixed;
            height: 100vh;
            overflow-y: auto;
            padding: 30px 20px;
        }}
        
        .sidebar-logo {{
            width: 120px;
            margin-bottom: 30px;
        }}
        
        .sidebar h2 {{
            font-size: 18px;
            font-weight: 700;
            margin-bottom: 25px;
            color: #CE0F69;
        }}
        
        .sidebar nav a {{
            display: flex;
            align-items: center;
            color: #e0e0e0;
            text-decoration: none;
            padding: 10px 0;
            font-size: 14px;
            transition: color 0.2s;
        }}
        
        .sidebar nav a:hover {{
            color: #CE0F69;
        }}
        
        .nav-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 10px;
        }}
        
        .dot-fail {{ background: #ef4444; }}
        .dot-pass {{ background: #22c55e; }}
        .dot-info {{ background: #3b82f6; }}
        
        .main-content {{
            margin-left: 260px;
            flex: 1;
            width: calc(100% - 260px);
        }}
        
        .hero {{
            background: linear-gradient(135deg, #CE0F69 0%, #7D2248 100%);
            color: #fff;
            padding: 60px 50px;
            position: relative;
        }}
        
        .hero h1 {{
            font-size: 32px;
            font-weight: 900;
            margin-bottom: 15px;
        }}
        
        .hero .subtitle {{
            font-size: 16px;
            font-weight: 300;
            opacity: 0.95;
        }}
        
        .badge {{
            display: inline-block;
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
            margin-top: 15px;
        }}
        
        .badge-fail {{
            background: #ef4444;
            color: #fff;
        }}
        
        .badge-pass {{
            background: #22c55e;
            color: #fff;
        }}
        
        .platform-thumb {{
            position: absolute;
            right: 50px;
            top: 50%;
            transform: translateY(-50%);
            width: 200px;
            height: auto;
            opacity: 0.3;
        }}
        
        .content-section {{
            padding: 50px;
        }}
        
        .content-section h2 {{
            color: #7D2248;
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 25px;
        }}
        
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .kpi-card {{
            background: #f1f1f1;
            border-radius: 8px;
            padding: 20px;
        }}
        
        .kpi-label {{
            font-size: 13px;
            color: #666;
            font-weight: 400;
            margin-bottom: 8px;
        }}
        
        .kpi-value {{
            font-size: 28px;
            font-weight: 700;
            color: #CE0F69;
        }}
        
        .kpi-unit {{
            font-size: 16px;
            color: #666;
            font-weight: 400;
        }}
        
        .callout {{
            border-left: 4px solid;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        
        .callout-critical {{
            background: #fef2f2;
            border-color: #ef4444;
        }}
        
        .callout-warning {{
            background: #fffbeb;
            border-color: #9a8300;
        }}
        
        .callout-info {{
            background: #eff6ff;
            border-color: #3b82f6;
        }}
        
        .callout-success {{
            background: #f0fdf4;
            border-color: #008a59;
        }}
        
        .callout-title {{
            font-weight: 700;
            margin-bottom: 8px;
            font-size: 14px;
        }}
        
        .callout-critical .callout-title {{ color: #ef4444; }}
        .callout-warning .callout-title {{ color: #9a8300; }}
        .callout-info .callout-title {{ color: #3b82f6; }}
        .callout-success .callout-title {{ color: #008a59; }}
        
        .chart-container {{
            width: 100%;
            height: 500px;
            margin: 30px 0;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        
        thead {{
            background: #CE0F69;
            color: #fff;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e5e5e5;
        }}
        
        tbody tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        
        tbody tr:hover {{
            background: #f1f1f1;
        }}
        
        .footer {{
            background: #2d2d2d;
            color: #ccc;
            text-align: center;
            padding: 30px;
            font-size: 13px;
        }}
        
        .footer strong {{
            color: #CE0F69;
        }}
    </style>
</head>
<body>
    <aside class="sidebar">
        <img src="https://companieslogo.com/img/orig/AKRBP.OL-c65af99e.png?t=1603469381" 
             alt="Aker BP" class="sidebar-logo">
        <h2>Blowdown Evaluation</h2>
        <nav>
            <a href="#overview"><span class="nav-dot dot-info"></span>Overview</a>
            <a href="#bs01"><span class="nav-dot dot-fail"></span>BS01</a>
            <a href="#bs02"><span class="nav-dot dot-fail"></span>BS02</a>
            <a href="#summary"><span class="nav-dot dot-info"></span>Summary</a>
        </nav>
    </aside>
    
    <main class="main-content">
        <div class="hero">
            <h1>Alvheim Blowdown Performance Evaluation</h1>
            <p class="subtitle">Segments BS01 & BS02 &bull; 11 January 2026</p>
            <span class="badge badge-fail">2 SEGMENTS FAIL</span>
            <img src="https://i0.wp.com/akerbp.com/wp-content/uploads/2023/06/08-alvheim4x.png?ssl=1" 
                 alt="Alvheim" class="platform-thumb">
        </div>
        
        <section id="overview" class="content-section">
            <h2>Overview</h2>
            <p style="margin-bottom: 20px;">
                This report evaluates the blowdown performance of segments <strong>BS01</strong> and 
                <strong>BS02</strong> on Alvheim against simulated depressurisation curves. 
                The acceptance criterion is <strong>&plusmn;{bs01['band_width']:.2f} barg (10% of P₀) around the theoretical curve</strong> 
                (the measured curve must stay within the green bands throughout).
            </p>
            
            <div class="callout callout-critical">
                <div class="callout-title">Critical Finding</div>
                Both segments depressurised significantly <strong>faster</strong> than the simulated 
                model predicts (reached 50% pressure 62&ndash;64 seconds earlier). The measured curves 
                breach the &plusmn;10% P₀ acceptance bands around the theoretical decay curves, with maximum 
                deviations of {bs01['max_dev']:.2f} barg ({bs01['max_percent_of_p0']:.1f}% of P₀) for BS01 
                and {bs02['max_dev']:.2f} barg ({bs02['max_percent_of_p0']:.1f}% of P₀) for BS02.
            </div>
            
            <table>
                <thead>
                    <tr>
                        <th>Segment</th>
                        <th>Tag Number</th>
                        <th>P₀ [barg]</th>
                        <th>Time to 50% (Meas)</th>
                        <th>Time to 50% (Theo)</th>
                        <th>Deviation</th>
                        <th>Max % Dev</th>
                        <th>Verdict</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>BS01</strong></td>
                        <td><code style="font-size: 11px; background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{bs01['external_id']}</code></td>
                        <td>{bs01['P0']:.2f}</td>
                        <td>{bs01['t_50_meas']:.1f} s</td>
                        <td>{bs01['t_50_theo']:.1f} s</td>
                        <td>{bs01['t_50_meas'] - bs01['t_50_theo']:.1f} s</td>
                        <td>{bs01['max_percent_of_p0']:.1f}%</td>
                        <td><span class="badge badge-fail">FAIL</span></td>
                    </tr>
                    <tr>
                        <td><strong>BS02</strong></td>
                        <td><code style="font-size: 11px; background: #f5f5f5; padding: 2px 6px; border-radius: 3px;">{bs02['external_id']}</code></td>
                        <td>{bs02['P0']:.2f}</td>
                        <td>{bs02['t_50_meas']:.1f} s</td>
                        <td>{bs02['t_50_theo']:.1f} s</td>
                        <td>{bs02['t_50_meas'] - bs02['t_50_theo']:.1f} s</td>
                        <td>{bs02['max_percent_of_p0']:.1f}%</td>
                        <td><span class="badge badge-fail">FAIL</span></td>
                    </tr>
                </tbody>
            </table>
        </section>
        
        <section id="bs01" class="content-section">
            <h2>BS01 Analysis</h2>
            <p style="margin-bottom: 20px; color: #666;"><strong>Tag:</strong> <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-size: 13px;">{bs01['external_id']}</code></p>
            
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">Starting Pressure</div>
                    <div class="kpi-value">{bs01['P0']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Decay Constant (k)</div>
                    <div class="kpi-value">{bs01['k']:.6f} <span class="kpi-unit">/s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Time Constant (τ)</div>
                    <div class="kpi-value">{bs01['tau']:.1f} <span class="kpi-unit">s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">RMSE</div>
                    <div class="kpi-value">{bs01['rmse']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
            </div>
            
            <div id="chart-bs01" class="chart-container"></div>
            
            <div class="callout callout-critical">
                <div class="callout-title">BS01 &mdash; FAIL</div>
                BS01 reached 50% of its starting pressure ({bs01['P0']/2:.2f} barg) in 
                <strong>{bs01['t_50_meas']:.1f} seconds</strong>, which is <strong>{bs01['t_50_theo'] - bs01['t_50_meas']:.1f} seconds 
                faster</strong> than the theoretical comparison curve predicts ({bs01['t_50_theo']:.1f} s). 
                The measured curve consistently tracks above the expected decay (less pressure retained), 
                indicating the segment vented more aggressively than modeled. Maximum deviation of 
                <strong>{bs01['max_dev']:.2f} barg ({bs01['max_percent_of_p0']:.1f}% of P₀)</strong> exceeds the 
                &plusmn;{bs01['band_width']:.2f} barg (10% of P₀) criterion.
                <br><br>
                <strong>Process safety interpretation:</strong> Faster-than-expected depressurisation 
                suggests the BDV may have opened wider than designed, the restriction orifice could be 
                missing or incorrectly sized, or gas composition/temperature differed from simulation 
                assumptions. Recommend inspection of BDV position feedback and orifice plate verification.
            </div>
        </section>
        
        <section id="bs02" class="content-section">
            <h2>BS02 Analysis</h2>
            <p style="margin-bottom: 20px; color: #666;"><strong>Tag:</strong> <code style="background: #f5f5f5; padding: 4px 8px; border-radius: 4px; font-size: 13px;">{bs02['external_id']}</code></p>
            
            <div class="kpi-grid">
                <div class="kpi-card">
                    <div class="kpi-label">Starting Pressure</div>
                    <div class="kpi-value">{bs02['P0']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Decay Constant (k)</div>
                    <div class="kpi-value">{bs02['k']:.6f} <span class="kpi-unit">/s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Time Constant (τ)</div>
                    <div class="kpi-value">{bs02['tau']:.1f} <span class="kpi-unit">s</span></div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">RMSE</div>
                    <div class="kpi-value">{bs02['rmse']:.2f} <span class="kpi-unit">barg</span></div>
                </div>
            </div>
            
            <div id="chart-bs02" class="chart-container"></div>
            
            <div class="callout callout-critical">
                <div class="callout-title">BS02 &mdash; FAIL</div>
                BS02 reached 50% of its starting pressure ({bs02['P0']/2:.2f} barg) in 
                <strong>{bs02['t_50_meas']:.1f} seconds</strong>, which is <strong>{bs02['t_50_theo'] - bs02['t_50_meas']:.1f} seconds 
                faster</strong> than the theoretical comparison curve predicts ({bs02['t_50_theo']:.1f} s). 
                Similar to BS01, the measured curve tracks above the expected decay throughout most of the 
                depressurisation, indicating excess vent capacity relative to the model. Maximum deviation 
                of <strong>{bs02['max_dev']:.2f} barg ({bs02['max_percent_of_p0']:.1f}% of P₀)</strong> exceeds the 
                &plusmn;{bs02['band_width']:.2f} barg (10% of P₀) criterion.
                <br><br>
                <strong>Process safety interpretation:</strong> The consistent pattern across both segments 
                (both ~64 s faster to 50% pressure) suggests a systematic deviation rather than isolated 
                equipment issues. This could indicate the simulation underestimated the BDV flow coefficient, 
                or operating conditions (gas temperature, composition) were different from design basis. 
                Recommend cross-check of simulation inputs against actual field conditions.
            </div>
        </section>
        
        <section id="summary" class="content-section">
            <h2>Summary & Recommendations</h2>
            
            <div class="callout callout-warning">
                <div class="callout-title">Key Findings</div>
                <ul style="margin-left: 20px; line-height: 1.8;">
                    <li>Both BS01 and BS02 <strong>FAIL</strong> the &plusmn;10% P₀ acceptance criterion (measured curves breach the bands)</li>
                    <li>Measured depressurisation rates are <strong>consistently faster</strong> than simulated (~44% faster to 50% pressure)</li>
                    <li>Maximum deviations: BS01 = {bs01['max_dev']:.2f} barg ({bs01['max_percent_of_p0']:.1f}% of P₀), BS02 = {bs02['max_dev']:.2f} barg ({bs02['max_percent_of_p0']:.1f}% of P₀)</li>
                    <li>Pattern is systematic across both segments, suggesting model vs. field mismatch rather than isolated equipment faults</li>
                </ul>
            </div>
            
            <div class="callout callout-info">
                <div class="callout-title">Recommended Actions</div>
                <ol style="margin-left: 20px; line-height: 1.8;">
                    <li><strong>Short-term:</strong> Verify BDV position feedback during blowdown events &mdash; confirm valves are not opening beyond design travel</li>
                    <li><strong>Short-term:</strong> Inspect restriction orifice plates on BS01 and BS02 vent lines &mdash; confirm correct size and installation</li>
                    <li><strong>Medium-term:</strong> Re-validate simulation inputs (gas composition, temperature, BDV Cv) against actual field measurements during the blowdown event</li>
                    <li><strong>Medium-term:</strong> Consider whether faster-than-expected depressurisation poses any process safety concerns (thermal shock, liquid carryover, flare capacity)</li>
                    <li><strong>Long-term:</strong> Update the dynamic model if field measurements consistently show faster decay across multiple events</li>
                </ol>
            </div>
            
            <p style="margin-top: 30px; color: #666; font-size: 14px;">
                <strong>Note:</strong> The theoretical comparison curves are anchored to each segment's 
                measured starting pressure at t=0 (BS01: {bs01['P0']:.2f} barg, BS02: {bs02['P0']:.2f} barg), 
                using the decay constant k from the dynamic simulation. This ensures the comparison reflects 
                how each segment <em>should have decayed from its actual starting point</em>, not from the 
                simulation's own initial pressure.
            </p>
        </section>
        
        <footer class="footer">
            <strong>PE Assistant</strong> &bull; Blowdown Performance Evaluator &bull; 
            22 June 2026 &bull; Norway time (CEST)
        </footer>
    </main>
    
    <script>
        // BS01 Chart
        var trace_meas_bs01 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs01['measured'].tolist())},
            mode: 'lines',
            name: 'Measured',
            line: {{color: '#ef4444', width: 2}}
        }};
        
        var trace_theo_bs01 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs01['theoretical'].tolist())},
            mode: 'lines',
            name: 'Theoretical (anchored to P₀)',
            line: {{color: '#3b82f6', width: 2, dash: 'dash'}}
        }};
        
        var trace_upper_bs01 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs01['upper_limit'].tolist())},
            mode: 'lines',
            name: 'Upper limit (+10%)',
            line: {{color: '#22c55e', width: 1, dash: 'dot'}},
            showlegend: true
        }};
        
        var trace_lower_bs01 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs01['lower_limit'].tolist())},
            mode: 'lines',
            name: 'Lower limit (−10%)',
            line: {{color: '#22c55e', width: 1, dash: 'dot'}},
            showlegend: true
        }};
        
        var layout_bs01 = {{
            title: 'BS01 &mdash; Measured vs Theoretical Comparison Curve',
            xaxis: {{
                title: 'Time [s]',
                gridcolor: '#e5e5e5'
            }},
            yaxis: {{
                title: 'Pressure [barg]',
                gridcolor: '#e5e5e5'
            }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: '#fff',
            font: {{family: 'Lato, sans-serif'}},
            legend: {{x: 0.7, y: 0.95}},
            hovermode: 'x unified'
        }};
        
        Plotly.newPlot('chart-bs01', [trace_meas_bs01, trace_theo_bs01, trace_upper_bs01, trace_lower_bs01], layout_bs01, {{responsive: true}});
        
        // BS02 Chart
        var trace_meas_bs02 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs02['measured'].tolist())},
            mode: 'lines',
            name: 'Measured',
            line: {{color: '#ef4444', width: 2}}
        }};
        
        var trace_theo_bs02 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs02['theoretical'].tolist())},
            mode: 'lines',
            name: 'Theoretical (anchored to P₀)',
            line: {{color: '#3b82f6', width: 2, dash: 'dash'}}
        }};
        
        var trace_upper_bs02 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs02['upper_limit'].tolist())},
            mode: 'lines',
            name: 'Upper limit (+10%)',
            line: {{color: '#22c55e', width: 1, dash: 'dot'}},
            showlegend: true
        }};
        
        var trace_lower_bs02 = {{
            x: {json.dumps(time_s.tolist())},
            y: {json.dumps(bs02['lower_limit'].tolist())},
            mode: 'lines',
            name: 'Lower limit (−10%)',
            line: {{color: '#22c55e', width: 1, dash: 'dot'}},
            showlegend: true
        }};
        
        var layout_bs02 = {{
            title: 'BS02 &mdash; Measured vs Theoretical Comparison Curve',
            xaxis: {{
                title: 'Time [s]',
                gridcolor: '#e5e5e5'
            }},
            yaxis: {{
                title: 'Pressure [barg]',
                gridcolor: '#e5e5e5'
            }},
            plot_bgcolor: '#fafafa',
            paper_bgcolor: '#fff',
            font: {{family: 'Lato, sans-serif'}},
            legend: {{x: 0.7, y: 0.95}},
            hovermode: 'x unified'
        }};
        
        Plotly.newPlot('chart-bs02', [trace_meas_bs02, trace_theo_bs02, trace_upper_bs02, trace_lower_bs02], layout_bs02, {{responsive: true}});
    </script>
</body>
</html>"""

# Save HTML report
output_path = 'OutputDataFiles/Alvheim_Blowdown_11Jan2026.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html)

print(f"HTML report generated: {output_path}")
