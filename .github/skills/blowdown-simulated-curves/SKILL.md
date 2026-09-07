---
name: blowdown-simulated-curves
description: Read and interpret simulated/theoretical topside blowdown curves from the supplied asset workbook.
argument-hint: Path to the simulated-curves .xlsx workbook and optionally a segment ID.
---

# Simulated Blowdown Curves

Read the simulated/theoretical pressure curve for each blowdown segment from the
asset workbook supplied by the user. This skill owns the theoretical side of the
comparison and does not retrieve measured data.

## Scope

Use this skill to load, parse, plot, or interpret a simulated curve; list which
segments were simulated; calculate time to a target pressure; or characterize the
exponential decay rate. The workbook path, worksheet name, segment set, time
range, and timestep are asset-specific and must be discovered from the file.
Do not infer them from another workbook.

## Rules

1. Use the parser in `scripts/parse_simulated_curves.py`; do not hand-roll an
   Excel read with a fixed header row.
2. Preserve simulated pressure values exactly as stored. Do not smooth, scale,
   round, resample, interpolate the curve itself, fill gaps, or replace values.
3. Use only rows with a numeric time value. Ignore all rows after the last valid
   timestep; blank-time rows are solver artifacts and are not curve data.
4. Treat `-` or an entirely empty segment column as not simulated. Drop it from
   curve analysis and report it as out of scope; never plot it as zero.
5. Use seconds and barg internally. Convert seconds to minutes only for display.
6. Do not assume a common segment set, time range, timestep, initial pressure,
   residual pressure, or worksheet name across assets.

## Data layout

The parser locates the segment-ID header by matching cells such as `BSnn` and
reads the time column and segment columns below it. A typical workbook contains
an offset title/note area, a row of segment IDs, and a numeric time column, but
the parser must remain the source of truth for the actual layout.

## Analytical model

The analysis helper fits the first-order model:

```text
P(t) = P0 * exp(-k * t)
```

where `P0` is barg, `k` is 1/s, and `tau = 1/k` is seconds. The fit is for
characterization and reporting only; it never replaces the stored curve.

```python
from parse_simulated_curves import load_simulated_curves, fit_exponential, exp_decay

res = load_simulated_curves("raw/<asset> Simulated Blowdown Curves.xlsx")
segment = res.segments[0]
fit = fit_exponential(res, segment)
model = exp_decay(res.time_s, fit["P0"], fit["k"])
```

`fit_exponential` returns `P0`, `k`, `tau`, `r2`, and `t_half`. Use
`time_to_pressure(res, segment, target_barg)` for time-to-target; interpolation
is permitted only to report a target crossing between existing samples and must
not alter the stored curve.

## Procedure

1. Select the supplied asset workbook under `raw/`, ignoring `~$` lock files.
2. Load it with `load_simulated_curves`.
3. Report the discovered worksheet, time range, timestep, simulated segments,
   and non-simulated segments.
4. For each requested segment, report starting pressure, ending pressure,
   decay-rate fit, fit quality, and target-crossing time when requested.
5. For HTML reporting, use the project reporting conventions and one separate
   chart per segment. Label axes `Time [s]` and `Pressure [barg]`.

## Environment

This is a `uv` project. Run Python through `uv run`; plain `python` is not
assumed to be available.

```powershell
$env:UV_LINK_MODE="copy"
uv run python ".github/skills/blowdown-simulated-curves/scripts/parse_simulated_curves.py" "raw/<asset> Simulated Blowdown Curves.xlsx"
```

## Boundaries

Do not retrieve measured data, map pressure tags, or issue PASS/REVIEW
performance verdicts here. Those belong to the measured-curve and performance-
evaluator skills. Do not modify files under `raw/`; write derived outputs to an
output directory.
