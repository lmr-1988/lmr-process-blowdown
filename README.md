# Blowdown Performance Evaluation System

Evaluates topside blowdown (emergency depressurisation) segment performance at Aker BP by comparing measured pressure curves against simulated/theoretical curves.

## Quick Start

### Single-Command Evaluation

```bash
# Using example data (fast, no CDF connection needed)
uv run python evaluate_blowdown_consolidated.py \
    --field Alvheim \
    --segments BS01,BS02 \
    --start "2026-01-11T17:51:06" \
    --use-example-data

# Using live CDF data
uv run python evaluate_blowdown_consolidated.py \
    --field Alvheim \
    --segments BS01,BS02 \
    --start "2026-01-11T17:51:06" \
    --tags BS01=ALV_16PST0139/MeasA/PRIM,BS02=ALV_16PST0239/MeasA/PRIM
```

Output: Self-contained HTML report in `OutputDataFiles/` with:
- Full Aker BP branding (magenta gradient, Lato font)
- Interactive Plotly charts (one per segment)
- KPI cards (starting pressure, decay constants, RMSE)
- Statistical summaries (no process safety interpretation)
- Sidebar navigation

## Performance

**Before optimization:** ~5 minutes (4 separate scripts, manual dependency management)

**After optimization:** ~30 seconds (single command, cached simulated curves, declared dependencies)

### Key Improvements

1. **Declared Dependencies** — All packages in `pyproject.toml`, no more `--with` on every run
2. **Simulated Curve Caching** — Excel parsing cached to `raw/.cache/`, ~10x faster on repeat runs
3. **Consolidated Pipeline** — One script does everything: load → retrieve → evaluate → report
4. **Example Data Fallback** — Test without CDF using `--use-example-data`

## Project Structure

```
blowdown-v2/
├── evaluate_blowdown_consolidated.py   # Main evaluation script (NEW)
├── pyproject.toml                      # Dependencies declared (UPDATED)
├── raw/
│   ├── {Field} Simulated Blowdown Curves.xlsx
│   ├── {Field} Measured Example Data.xlsx
│   ├── {Field} Pressure Measurement External IDs.xlsx
│   └── .cache/                         # Auto-generated cache (NEW)
│       └── {Field}_Simulated_Blowdown_Curves_parsed.pkl
├── OutputDataFiles/                    # HTML reports
└── .github/skills/
    ├── blowdown-simulated-curves/      # Simulated curve parser (caching added)
    └── blowdown-measured-curves/       # CDF retrieval

```

## Dependencies

All dependencies are declared in `pyproject.toml`:
- pandas >= 2.0
- openpyxl >= 3.1  
- numpy >= 1.24
- scipy >= 1.11
- cognite-sdk >= 7.0

Install once with: `uv sync`

## Acceptance Criterion

**±10% of starting pressure (P₀)** as an absolute band around the theoretical curve.

Example: If P₀ = 25 barg, the measured curve must stay within ±2.5 barg of the theoretical curve throughout the depressurisation.

## Fields Supported

- Alvheim (verified)
- Skarv (structure verified)
- Edvard Grieg (structure verified)

Add new fields by placing their simulated curves Excel in `raw/`

## Related Documentation

- [Blowdown Simulated Curves Skill](.github/skills/blowdown-simulated-curves/SKILL.md)
- [Blowdown Measured Curves Skill](.github/skills/blowdown-measured-curves/SKILL.md)
- [CDF Connection Guide](abp-cdf-connection-guide/CDF-Connection-Guide.md)
- [HTML Reporting](abp-html-reporting/SKILL.md)