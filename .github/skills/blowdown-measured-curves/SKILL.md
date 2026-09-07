---
name: blowdown-measured-curves
description: "Retrieve the MEASURED topside blowdown (depressurisation) pressure curve per segment (BSxx) for any Aker BP field from Cognite Data Fusion (CDF). The field's segment-to-instrument tag (external_id) comes from Enlight or the user. Use when the user asks to load, pull, plot, or get the measured/actual pressure-vs-time for a blowdown segment around an event, the real pressure transmitter signal, or the as-happened depressurisation. Returns a clean time[s] vs pressure[barg] curve at raw resolution, localised to Norway time. NEVER alters the measured values — the only reduction allowed for extremely dense data is value-preserving decimation (a subset of real samples)."
argument-hint: "Field + segment(s) (BSxx) + blowdown event time window, plus the pressure-transmitter external_id (or let Enlight resolve it)"
---

# Measured Blowdown Curves — Retriever

## Purpose

Pull the **measured / actual** blowdown pressure curve for a segment (`BSxx`)
from **Cognite Data Fusion (CDF)** — the real pressure-transmitter time series
around a depressurisation event — and return clean **time [s] vs pressure [barg]**
data, one curve per segment, localised to **Europe/Oslo**. This skill owns the
*measured* side of blowdown evaluation; the simulated/theoretical side is the
`blowdown-simulated-curves` skill.

**Field-agnostic.** Works for any Aker BP field. The field is selected through
its CDF project (`abp`) and the segment's pressure-transmitter `external_id`
(resolved via Enlight or supplied by the user) — nothing here is hardcoded to one
asset.

## When to Use

 - "Get / pull / load the **measured** blowdown curve for a requested segment."
 - "What did the pressure actually do during a segment blowdown on \<date/time\>?"
- "Plot the real pressure-transmitter signal around the blowdown event."
- "Retrieve the measured depressurisation for these segments."
          external_id="<pressure-transmitter-external-id>",
          segment="<segment-id>",
          client, {"<segment-a>": "<external-id-a>", "<segment-b>": "<external-id-b>"},
curve it consumes.

    uv run python ".github/skills/blowdown-measured-curves/scripts/retrieve_measured_curves.py" "<external-id>" "<start-time>" "<end-time>" --segment "<segment-id>"
## Inviolable Rules

 Pressure-transmitter tags are asset-specific external IDs supplied by the user
 or resolved through the approved mapping source.
   **raw CDF measurements** — no averaging, smoothing, scaling, rounding,
   interpolation, gap-filling, or server-side aggregation. Reading is the only
   operation on the values.
2. **Retrieve at raw resolution.** A blowdown lasts seconds-to-minutes. Use
   **raw datapoints** — never CDF aggregates (`average`, `1h`, …). Coarse
   aggregates destroy the depressurisation transient and are forbidden here.
3. **Filtering = value-preserving decimation only.** If, and only if, the window
   returns **extremely dense** data, you may reduce the point count by selecting a
   **subset of the original samples** (LTTB). Every point kept is an unmodified
   real measurement; peaks and the steep decay are preserved. You may **not**
   average/bin/smooth to thin the data (that fabricates values). See below.
4. **Norway time, always.** Localise timestamps to **Europe/Oslo**, never present
   UTC. The user's event time is Norway local.
5. **Read-only, interactive auth.** CDF access is browser OAuth interactive
   (project `abp`); no secrets, no client-credential flow, no writes.

## What "filtering" means here (allowed vs forbidden)

| Allowed (value-preserving) | Forbidden (alters data) |
|----------------------------|-------------------------|
| LTTB / min-max **decimation** — keep a *subset* of the real samples | `average`/`mean`/binned **aggregation** (CDF `aggregates=`/`granularity=`) |
| Dropping `NaN` / empty datapoints | Smoothing / rolling mean / low-pass filtering |
| Trimming to the requested time window | Interpolation / resampling onto a new grid |
| Sorting by time, de-duplicating identical timestamps | Rounding / scaling / unit re-baselining of values |

Rule of thumb: **every value in the output must be a number that CDF actually
returned.** Decimation changes *how many* points you keep, never *what* a point's
value is. Use it only when the raw pull is so dense it impedes plotting/analysis;
otherwise return every raw sample.

## Data Source & Access

| Source | What it gives you | Guide |
|--------|-------------------|-------|
| **CDF** | Measured pressure time series (raw datapoints) per `external_id` | `abp-cdf-connection-guide` (OAuth interactive, project `abp`, cluster `az-ams-sp-002`) |
| **Enlight** | Segment ↔ instrument mapping → `external_id`, operating limits | `abp-enlight-connection-guide` (corporate network, no token) |

**Enlight** tells you *which* pressure transmitter belongs to a segment (its
`external_id`); **CDF** gives the *actual values*. If the user already provides
the `external_id`, you can skip Enlight. Pressure-transmitter identifiers are
asset-specific and must come from the approved mapping source or the user.

## Procedure

1. **Scope the request.** Identify the field, the segment(s) (`BSxx`), and the
   **event time window** (Norway time). Keep the window tight around the blowdown
   so the transient is not buried in steady-state data.
2. **Resolve the tag.** Get each segment's pressure-transmitter `external_id`
   from the user, or via Enlight (`well.instrumentation` → `external_id`). If a
   tag is unknown, use `search_pressure_tags(client, "<PT name>")` as a discovery
   fallback and **confirm** before trusting it.
3. **Retrieve (raw, value-preserving)** with the provided script — it encodes
   every rule above (raw datapoints, Oslo tz, optional LTTB thinning). Do **not**
   hand-roll an aggregated `retrieve_dataframe`:
   [scripts/retrieve_measured_curves.py](./scripts/retrieve_measured_curves.py)
   ```python
   from retrieve_measured_curves import (
       cdf_interactive_client, retrieve_measured_curve, retrieve_measured_curves,
   )

   client = cdf_interactive_client()                 # browser login (cached)
      curve = retrieve_measured_curve(
         client,
         external_id="<pressure-transmitter-external-id>",
         start="<start-time>",                          # Norway time
         end="<end-time>",
         segment="<segment-id>",
       # max_points=6000 default → LTTB thins ONLY if denser; None = never thin
   )
   curve.time_s        # seconds from t0 (first sample, or a t0 you pass)
   curve.pressure      # barg, raw measured values (or a real subset)
   curve.frame         # tidy DataFrame indexed by Europe/Oslo timestamp
   curve.n_raw, curve.n_returned, curve.thinned   # transparency on decimation

   # several segments at once: {segment: external_id} -> {segment: MeasuredCurve}
      curves = retrieve_measured_curves(
         client, {"<segment-a>": "<external-id-a>", "<segment-b>": "<external-id-b>"},
         start="<start-time>", end="<end-time>",
   )
   ```
4. **Sanity-check the pull.** Confirm the unit is **barg**, the window actually
   contains the decay (pressure falls), and report `n_raw → n_returned` so any
   decimation is transparent. Flag gaps or flatlines rather than papering over
   them.
5. **Report / plot** as requested.
   - **All reporting is HTML.** Produce a self-contained, Aker BP–branded report
     via the `abp-html-reporting` skill — never a bare PNG/PDF. Save to
     `OutputDataFiles/{Asset}_Measured_{DDMmmYYYY}.html`.
   - **One separate plot per segment** — never combine segments on one chart.
     Plot `curve.time_s` (or `/60` for minutes) vs `curve.pressure`; label axes
     `Time` and `Pressure [barg]`.

## Environment

This is a **uv** project (Python ≥ 3.14). All dependencies (cognite-sdk, pandas, numpy) are declared in `pyproject.toml`.

Run via:

```powershell
$env:UV_LINK_MODE="copy"   # avoids a Windows hardlink error (os error 396)
uv run python ".github/skills/blowdown-measured-curves/scripts/retrieve_measured_curves.py" "<external-id>" "<start-time>" "<end-time>" --segment "<segment-id>"
```

The CLI opens a browser for interactive CDF login on first run. Plain `python` is
not on PATH — always go through `uv run`.

## Critical CDF SDK API Notes

**Three key API behaviors** (validated June 2026):

1. **Timestamp conversion**: The `.retrieve()` API requires **millisecond epoch timestamps**, not datetime objects:
   ```python
   start_ms = int(start.timestamp() * 1000)  # datetime → ms since epoch
   end_ms = int(end.timestamp() * 1000)
   df = client.time_series.data.retrieve(external_id=ext_id, start=start_ms, end=end_ms)
   ```

2. **DataFrame column access**: Returned DataFrame columns are **`(NodeId, unit)` tuples**, not strings. Access data via **positional indexing**:
   ```python
   # WRONG: df[external_id] - fails (column name is a tuple)
   # RIGHT: df.iloc[:, 0] - gets first (only) column
   series = df.iloc[:, 0].dropna()
   ```

3. **Per-segment time arrays**: Different segments have different sampling rates/densities. Return **per-segment time arrays** from `retrieve_measured_curves()`, not a single shared time base:
   ```python
   # Each segment gets its own time_s and pressure arrays
   return {segment: MeasuredCurve(time_s=seg_time, pressure=seg_pressure, ...)}
   ```

These fixes are **critical** — without them, CDF data retrieval fails with AttributeError or returns empty results.

## Do Not

- Do **not** modify, smooth, scale, round, resample, or interpolate the measured
  values — return them **exactly** as CDF reports them.
- Do **not** use CDF aggregates / granularity (hourly or otherwise) for the
  curve — raw datapoints only.
- Do **not** thin data by averaging/binning — decimation must keep real samples
  (LTTB), and only when the data is extremely dense.
- Do **not** present UTC timestamps — localise to Europe/Oslo.
- Do **not** use client-credential auth or hardcode secrets — interactive browser
  login only; CDF is read-only.
- Do **not** combine multiple segments on one chart — one separate plot per
  segment.
- Do **not** compute the PASS/FAIL verdict or align against the simulated curve
  here — that is the evaluator agent's job; this skill only retrieves the
  measured curve.

## Package Contents

- [scripts/retrieve_measured_curves.py](./scripts/retrieve_measured_curves.py) —
  CDF interactive client, raw measured-curve retrieval (`retrieve_measured_curve`,
  `retrieve_measured_curves`), value-preserving LTTB decimation (`lttb_indices`),
  a tag-search fallback (`search_pressure_tags`), and a CLI summary.
