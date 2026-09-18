"""Generate a branded HTML overview of exponential fits to Skarv simulations."""

import json
import sys
from datetime import date
from html import escape
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

sys.path.append(".github/skills/blowdown-simulated-curves/scripts")
from parse_simulated_curves import exp_decay, fit_exponential, load_simulated_curves


SOURCE = Path("raw/Skarv Simulated Blowdown Curves.xlsx")
OUTPUT = Path("OutputDataFiles/Skarv_Simulated_15Sep2026.html")


def main() -> None:
    result = load_simulated_curves(str(SOURCE), use_cache=False)

    def anchored_fit(segment: str) -> dict[str, float]:
        """Fit k while forcing the analytical curve through the first sample."""
        initial_pressure = result.initial_pressure[segment]
        observed = result.curves[segment].astype(float)
        initial_fit = fit_exponential(result, segment)
        (k,), _ = curve_fit(
            lambda time_s, rate: initial_pressure * np.exp(-time_s * rate),
            result.time_s,
            observed,
            p0=[initial_fit["k"]],
            bounds=([1e-9], [1e3]),
            maxfev=200000,
        )
        fitted = initial_pressure * np.exp(-result.time_s * k)
        ss_res = float(np.sum((observed - fitted) ** 2))
        ss_tot = float(np.sum((observed - np.mean(observed)) ** 2))
        return {
            "P0": initial_pressure,
            "k": float(k),
            "tau": float(1.0 / k),
            "r2": 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
            "t_half": float(np.log(2.0) / k),
        }

    fits = {segment: anchored_fit(segment) for segment in result.segments}
    r2_values = np.array([fit["r2"] for fit in fits.values()])
    below_99 = [segment for segment, fit in fits.items() if fit["r2"] < 0.99]

    rows = []
    charts = []
    for index, segment in enumerate(result.segments, start=1):
        fit = fits[segment]
        observed = result.curves[segment]
        fitted = exp_decay(result.time_s, fit["P0"], fit["k"])
        residual = observed - fitted
        rmse = float(np.sqrt(np.mean(residual ** 2)))
        max_abs = float(np.max(np.abs(residual)))
        rows.append(
            f"<tr><td>{escape(segment)}</td><td>{result.initial_pressure[segment]:.3f}</td>"
            f"<td>{result.final_pressure[segment]:.3f}</td><td>{fit['k']:.6g}</td>"
            f"<td>{fit['tau']:.1f}</td><td>{fit['t_half']:.1f}</td>"
            f"<td>{fit['r2']:.5f}</td><td>{rmse:.3f}</td><td>{max_abs:.3f}</td></tr>"
        )
        equation = f"P(t) = {fit['P0']:.3g} \u00d7 e^(-{fit['k']:.4g}\u00b7t)"
        charts.append({
            "id": f"chart-{index}", "segment": segment,
            "time": result.time_s.tolist(), "observed": observed.tolist(),
            "fitted": fitted.tolist(), "r2": fit["r2"], "equation": equation,
        })

    chart_json = json.dumps(charts, separators=(",", ":"))
    outlier_text = (
        "All segment fits have R&sup2; &ge; 0.99."
        if not below_99 else "Below R&sup2; = 0.99: " + ", ".join(below_99) + "."
    )
    chart_sections = "".join(
        f'<div class="chart-card"><div class="chart-title"><h3>{escape(item["segment"])}</h3>'
        f'<span>{escape(item["equation"])} &bull; R&sup2; = {item["r2"]:.5f}</span></div>'
        f'<div id="{item["id"]}" class="chart"></div></div>'
        for item in charts
    )
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skarv Simulated Curve Fit Overview</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lato:wght@300;400;700;900&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{ --pink:#CE0F69; --heading:#7D2248; --ink:#2d2d2d; --muted:#68707a; --line:#e4e7eb; --card:#f4f5f6; }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family:Lato,sans-serif; color:var(--ink); background:#fff; display:flex; }}
.sidebar {{ width:240px; min-height:100vh; position:fixed; background:#292929; color:#fff; padding:28px 20px; }}
.sidebar h2 {{ color:var(--pink); font-size:20px; margin:12px 0 28px; }} .sidebar p {{ color:#c7c7c7; font-size:13px; line-height:1.5; }}
.sidebar a {{ color:#eee; display:block; padding:9px 0; text-decoration:none; font-size:14px; }} .sidebar a:hover {{ color:#ff83b4; }}
main {{ margin-left:240px; width:calc(100% - 240px); }} .hero {{ padding:48px 54px; color:#fff; background:linear-gradient(125deg,#CE0F69,#7D2248); }}
.hero h1 {{ margin:0 0 8px; font-size:34px; }} .hero p {{ margin:0; opacity:.9; }} section {{ padding:38px 54px; }} h2 {{ color:var(--heading); margin:0 0 20px; }}
.kpis {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:16px; }} .kpi {{ background:var(--card); padding:18px; border-radius:8px; }}
.label {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; }} .value {{ color:var(--pink); font-size:25px; font-weight:700; margin-top:6px; }}
.callout {{ margin:22px 0; padding:15px 18px; border-left:4px solid var(--pink); background:#fff2f7; }}
.table-wrap {{ overflow:auto; }} table {{ width:100%; border-collapse:collapse; font-size:13px; }} th {{ background:var(--pink); color:#fff; text-align:left; }} th,td {{ padding:10px 11px; border-bottom:1px solid var(--line); white-space:nowrap; }} tr:nth-child(even) {{ background:#fafafa; }}
.chart-card {{ border-top:1px solid var(--line); padding:28px 0 35px; }} .chart-title {{ display:flex; justify-content:space-between; gap:12px; align-items:baseline; }} .chart-title h3 {{ color:var(--heading); margin:0; }} .chart {{ height:390px; }} footer {{ padding:25px 54px; background:#292929; color:#bbb; font-size:12px; }}
@media(max-width:720px) {{ .sidebar {{ position:static; width:100%; min-height:auto; }} body {{ display:block; }} main {{ margin:0; width:100%; }} .hero,section,footer {{ padding:30px 20px; }} .chart {{ height:330px; }} }}
</style></head><body>
<aside class="sidebar"><h2>Blowdown Buddy</h2><p>Skarv simulated curve-fit overview</p><nav><a href="#summary">Summary</a><a href="#table">Fit table</a><a href="#curves">Curve fits</a></nav></aside>
<main><header class="hero"><h1>Skarv simulated curve fits</h1><p>Exponential model review &bull; {len(result.segments)} simulated segments &bull; {result.time_s[-1]:.0f} s window</p></header>
<section id="summary"><h2>Fit summary</h2><div class="kpis"><div class="kpi"><div class="label">Segments</div><div class="value">{len(result.segments)}</div></div><div class="kpi"><div class="label">Median R&sup2;</div><div class="value">{np.median(r2_values):.5f}</div></div><div class="kpi"><div class="label">Minimum R&sup2;</div><div class="value">{np.min(r2_values):.5f}</div></div><div class="kpi"><div class="label">Time step</div><div class="value">{result.dt_s:.0f} s</div></div></div><div class="callout"><strong>Interpretation:</strong> Each exponential fit is anchored to the workbook pressure at t = 0 and fits only the decay rate. {outlier_text} The fit is analytical only; the workbook values remain the source curve.</div></section>
<section id="table"><h2>Segment fit parameters</h2><div class="table-wrap"><table><thead><tr><th>Segment</th><th>P0 [barg]</th><th>Pend [barg]</th><th>k [1/s]</th><th>&tau; [s]</th><th>t&frac12; [s]</th><th>R&sup2;</th><th>RMSE [barg]</th><th>Max abs. residual [barg]</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section id="curves"><h2>Observed curves and exponential fits</h2>{chart_sections}</section>
<footer>Blowdown Buddy &bull; Skarv simulated data &bull; Generated 15 Sep 2026 &bull; Norway time</footer></main>
<script>const charts={chart_json}; charts.forEach(c=>Plotly.newPlot(c.id,[{{x:c.time,y:c.observed,name:'Workbook simulation',mode:'lines',line:{{color:'#CE0F69',width:2}}}},{{x:c.time,y:c.fitted,name:'Exponential fit',mode:'lines',line:{{color:'#2563eb',width:2,dash:'dash'}}}}],{{margin:{{l:58,r:20,t:34,b:48}},hovermode:'x unified',xaxis:{{title:'Time [s]'}},yaxis:{{title:'Pressure [barg]'}},legend:{{orientation:'h',y:1.12}},annotations:[{{xref:'paper',yref:'paper',x:0.99,y:0.97,xanchor:'right',yanchor:'top',showarrow:false,text:c.equation,font:{{family:'Lato,sans-serif',size:13,color:'#2563eb'}},bgcolor:'rgba(255,255,255,0.85)',bordercolor:'#2563eb',borderwidth:1,borderpad:4}}],paper_bgcolor:'white',plot_bgcolor:'white'}},{{responsive:true,displaylogo:false}}));</script>
</body></html>"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT}")
    print(f"Segments: {len(result.segments)}; median R2: {np.median(r2_values):.5f}; min R2: {np.min(r2_values):.5f}")
    print(f"Lowest-fit segment: {result.segments[int(np.argmin(r2_values))]}")


if __name__ == "__main__":
    main()