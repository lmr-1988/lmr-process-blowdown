# Blowdown Evaluation System — Project Memory

## Overview
Topside blowdown performance evaluator for Aker BP — compares measured vs theoretical (simulated) depressurisation curves per segment (BSxx) and issues status assessments (**PASS / REVIEW / INCONCLUSIVE**).

**Status Definitions:**
- **PASS** = measured curve stays within acceptance criteria throughout
- **REVIEW** = measured curve exceeds acceptance criteria (requires engineering review)
- **INCONCLUSIVE** = data is missing, the event is ambiguous, or the segment was not simulated

## Architecture

### Agent: Blowdown Performance Evaluator
**File:** `.github/agents/blowdown-performance.agent.md`

**Core methodology:**
- **Theoretical comparison curve** = `P_theo(t) = P0_measured · exp(−k_sim · t)`
  - `P0_measured` = segment's measured pressure at the user-supplied blowdown initiation time
  - `k_sim` = decay constant from the dynamic simulation (via exponential fit)
  - This anchors the expected curve to where the segment **actually started**, not the simulation's own P0
- **Status:** compare measured vs theoretical per user-supplied acceptance criteria
  - Default criterion (if user provides): ±10% of P0 as **absolute band** (e.g., P0=25 barg → ±2.5 barg around theoretical curve)
  - Never multiplicative (theo × 1.10), always absolute offset (theo ± 0.10·P0)

**Mandatory inputs (ALWAYS required):**
1. **Blowdown initiation time** (Europe/Oslo) — user must supply; never auto-detect or infer. This is both:
   - `t = 0` for the evaluation timeline
   - The start time from which measured pressure is retrieved from CDF (retrieval begins exactly there)
2. **Acceptance criteria** per segment — e.g. "±10% of theoretical curve", "reach X barg within Y min"

**Field-agnostic** — works for Alvheim, Skarv, Edvard Grieg, etc. via workbook/tag selection.

### Skills

#### 1. blowdown-simulated-curves
**File:** `.github/skills/blowdown-simulated-curves/SKILL.md`  
**Script:** `.github/skills/blowdown-simulated-curves/scripts/parse_simulated_curves.py`

Reads `raw/<Field> Simulated Blowdown Curves.xlsx` and produces clean time[s] vs pressure[barg] per segment.

**Key functions:**
- `load_simulated_curves(path, use_cache=True)` → `SimulatedCurves` (frame, time_s, curves dict, segments, not_simulated, initial/final_pressure)
  - **Caching:** First parse ~8s, cached reads ~0.3s (27× faster). Cache stored in `raw/.cache/{field}_parsed.pkl`, auto-invalidated on Excel mtime change.
- `fit_exponential(res, segment)` → `{P0, k, tau, r2, t_half}` — fits P(t) = P0·exp(−kt)
- `exp_decay(t, P0, k)` → analytical curve for any P0 (used to build theoretical comparison)
- `time_to_pressure(res, segment, target_barg)` → first time curve reaches ≤ target (or None)

**Inviolable rules:**
1. Never modify simulated curve values — use exactly as in Excel
2. Ignore rows after the last timestep (trailing artifact rows with blank time)

**Gotchas handled:**
- Offset header (segment IDs row 3, data row 4)
- Non-simulated segments marked `-` → NaN → dropped
- Trailing artifact rows (blank time, discontinuous jumps) → only keep rows with valid numeric time
- Not all segments reach ~0 within the window (residuals are legitimate)

**Model:** First-order exponential decay, R² ≥ 0.99 for all Alvheim segments.

#### 2. blowdown-measured-curves
**File:** `.github/skills/blowdown-measured-curves/SKILL.md`  
**Script:** `.github/skills/blowdown-measured-curves/scripts/retrieve_measured_curves.py`

Retrieves measured pressure curves from CDF at **raw resolution** (no aggregates).

**Key functions:**
- `cdf_interactive_client()` → CogniteClient (OAuth interactive, project `abp`, no secrets)
- `retrieve_measured_curve(client, external_id, start, end, segment=None, t0=None, max_points=6000)` → `MeasuredCurve`
- `retrieve_measured_curves(client, segment_tags_dict, start, end, t0=None, max_points=6000)` → `{segment: MeasuredCurve}`
- `lttb_indices(x, y, n_out)` → value-preserving decimation (Largest-Triangle-Three-Buckets)

**Critical CDF SDK API behaviors (validated Jun 2026):**
1. **DateTime → milliseconds:** `.retrieve()` requires `int(dt.timestamp() * 1000)`, not datetime objects
2. **DataFrame columns are tuples:** Returned columns are `(NodeId, unit)` tuples → access via `df.iloc[:, 0]`, not `df[external_id]`
3. **Per-segment time arrays:** Different segments have different sampling rates → return per-segment time arrays, not a shared time base

**Inviolable rules:**
1. Never alter measured values — no averaging, smoothing, interpolation
2. Raw datapoints only — never use CDF aggregates/granularity
3. Only permitted reduction: LTTB decimation (keeps real samples, preserves peaks) when extremely dense
4. Localise to Europe/Oslo, never present UTC
5. Read-only, interactive browser auth

**Data source:** CDF project `abp`, cluster `az-ams-sp-002`. 

**Segment → external_id mapping:**
1. **Excel mapping file** (recommended): `raw/{Field} Pressure Measurement External IDs.xlsx` (no headers, col 0=segment, col 1=external_id)
   - Example: `BS01 | ALV_16PST0139/MeasA/PRIM`
   - Alvheim: 31 segment mappings (BS01-BS20, BS25-BS35)
2. **Enlight API:** Query instrumentation endpoint
3. **User-supplied:** Accept external_id directly from user

## Data Locations

```
raw/
  Alvheim Simulated Blowdown Curves.xlsx              # theoretical (31 simulated, 4 not)
  Alvheim Pressure Measurement External IDs.xlsx     # segment → CDF external_id mapping (31 mappings)
  .cache/
    Alvheim_parsed.pkl                                # cached simulated curves (auto-invalidated)
  
evaluate_blowdown_consolidated.py                   # RECOMMENDED: single-command evaluation pipeline

.github/
  agents/
    blowdown-performance.agent.md          # main evaluator agent
  skills/
    blowdown-simulated-curves/
      SKILL.md
      scripts/parse_simulated_curves.py
      references/alvheim-segments.md       # verified inventory
    blowdown-measured-curves/
      SKILL.md
      scripts/retrieve_measured_curves.py

OutputDataFiles/
  {Asset}_Blowdown_{DDMmmYYYY}.html        # branded reports
```

## Key Design Decisions

### Why anchor theoretical to measured P0?
Segments may start at different pressures than simulated due to operating conditions. Anchoring to the measured starting pressure means we're testing "did it decay at the expected rate from where it actually was?" — not penalising for a different P0. Only `k` (decay rate) comes from simulation.

### Acceptance criteria handling
Never hardcode criteria — they're segment-specific and safety-critical. Always ask the user if not provided.

### Tail pressure issue (solved)
At very low pressures (< 10% of P0), theoretical curves approach zero while measured data may have small residuals. Computing `(P_meas − P_theo) / P_theo` gives huge percentages. **Solution:** only apply the percentage criterion in the **main depressurisation zone** (P > 10% of P0). Below that, the segment has essentially blown down.

### Field-agnostic design
- Simulated curves: workbook filename identifies field → auto-detects header/segments/time base per file
- Measured curves: via CDF external_id (resolved from Enlight or user)
- Nothing hardcoded to Alvheim

## Environment

- **uv** project (Python ≥ 3.14), `pyproject.toml`
- **All dependencies declared** in `pyproject.toml` (pandas ≥2.0, openpyxl ≥3.1, numpy ≥1.24, scipy ≥1.11, cognite-sdk ≥7.0)
- Run via `uv run python ...` — no `--with` flags needed
- Plain `python` not on PATH — always go through `uv run`
- Windows: prefix `$env:UV_LINK_MODE="copy"` to avoid hardlink error (os error 396)

### Consolidated Evaluation Script (RECOMMENDED)

**`evaluate_blowdown_consolidated.py`** — single-command pipeline for complete evaluations (~600 lines):

```powershell
uv run python evaluate_blowdown_consolidated.py \
  --field Alvheim \
  --segments BS01,BS02,BS07 \
  --start "2026-01-11T17:51:06" \
  --end "2026-01-11T18:51:06"
```

**Features:**
- Loads simulated curves with caching (~27× speedup: 8s → 0.3s)
- Auto-loads external IDs from `raw/{Field} Pressure Measurement External IDs.xlsx`
- Retrieves measured data from CDF (OAuth interactive)
- Evaluates all segments with per-segment acceptance criteria
- Generates full Aker BP-branded HTML report (Blowdown Buddy)
- **Performance:** Full 31-segment evaluation in ~30 seconds (with cache) vs ~5 minutes (original workflow)

**Options:**
- `--use-example-data`: Use synthetic data instead of CDF (testing)
- `--no-cache`: Bypass simulated curves cache (force re-parse)
- `--tags`: Override external ID mapping from CLI

## Output Format

**HTML reports only** (never bare PNG/PDF). Aker BP branded:
- Branding: **"Blowdown Buddy"** (not "PE Assistant")
- Magenta accent `#CE0F69`, dark magenta `#7D2248`
- Lato font (Google Fonts)
- Fixed sidebar nav, gradient hero, KPI cards, callouts, lazy-loaded Plotly charts
- **One separate chart per segment** — never combine segments
- Per segment: 
  - **PASS / REVIEW / INCONCLUSIVE** status badge (not "verdict")
  - **Tag number** (CDF external_id) displayed
  - Chart: theoretical comparison curve (±acceptance bands) vs measured pressure vs time
  - KPIs: P0 (measured), k/tau (simulated), max/mean deviation, RMSE, time-to-target (theoretical vs measured)
  - **Statistical summary only** — no process safety interpretation (objective metrics + status only)

## Example Evaluations

### Full 31-segment evaluation (Alvheim, live CDF data)

Ran 11 Jan 2026 at timestamp 18:51:06 (Europe/Oslo):
- Initiation time: 2026-01-11 18:51:06
- Acceptance: ±10% of P0 as absolute band
- Result: **5 PASS, 26 REVIEW**
  - PASS segments: BS06, BS15, BS32, BS33, BS34 (deviations 3.2% to 9.9%)
  - REVIEW segments: BS01-BS05, BS07-BS14, BS16-BS20, BS25-BS31, BS35 (deviations 10.3% to 99.2%)
- Report: `OutputDataFiles\Alvheim_Blowdown_11_Jan_2026.html`
- Performance: ~30 seconds with cache, includes CDF OAuth, data retrieval, evaluation, HTML generation

**Note:** Earlier timestamp (17:51:06) produced 0 PASS, 31 REVIEW — timing matters for blowdown event capture.

## Related Guides

- `abp-cdf-connection-guide/` — OAuth interactive CDF access, project `abp`
- `abp-enlight-connection-guide/` — segment → instrument mapping
- `abp-html-reporting/` — branded HTML template conventions

## Lessons Learned (Validated June 2026)

### Acceptance Criteria: Absolute vs Multiplicative
**Problem:** Initial implementation used multiplicative bands (`theo × 1.10`) which don't follow the theoretical curve shape — they expand/contract with pressure.  
**Solution:** Use **absolute offset bands** (`theo ± 0.10 × P0`), where the band width is fixed based on the starting pressure. This creates parallel lines around the theoretical curve that are constant throughout the decay.

### CDF SDK API Changes (Critical)
Three API behaviors that will break data retrieval if not handled:

1. **DateTime to milliseconds:** The `.retrieve()` method requires epoch milliseconds, not datetime objects:
   ```python
   start_ms = int(start.timestamp() * 1000)  # REQUIRED
   df = client.time_series.data.retrieve(external_id=ext_id, start=start_ms, end=end_ms)
   ```

2. **DataFrame column structure:** Returned columns are `(NodeId, unit)` tuples, not string external_ids:
   ```python
   # WRONG: df[external_id] - fails
   # RIGHT: df.iloc[:, 0] - positional indexing
   ```

3. **Per-segment time arrays:** Different segments have different sampling rates. Return separate time arrays per segment, not a shared time base.

### Performance Optimization
**Original workflow:** ~5 minutes for 31 segments (sequential script calls, repeated Excel parsing)  
**Optimizations applied:**
1. Declare dependencies in `pyproject.toml` → eliminates `--with` flags overhead
2. Implement simulated curves caching → 8s to 0.3s (27× speedup)
3. Consolidate into single script → eliminates inter-script overhead
4. **Result:** ~30 seconds for full 31-segment evaluation (~10× faster)

### External ID Management
**Anti-pattern:** Generating placeholder tags like `ALVHEIM_PT_BS07` when external_ids are unknown.  
**Best practice:** Load from Excel mapping file (`raw/{Field} Pressure Measurement External IDs.xlsx`) or ask user — never fabricate tags that won't exist in CDF.

### Unicode in Console Output (Windows)
**Problem:** `print(f"tau = {tau}τ")` fails on Windows PowerShell with encoding errors.  
**Solution:** Use ASCII-safe output for console (`tau` not `τ`), save Unicode for HTML reports only.

### Terminology Standardization
**Process safety convention:**
- Use **"status"** not "verdict" (less judgmental)
- **PASS** = meets criteria
- **REVIEW** = exceeds criteria (requires engineering review, not automatic "failure")
- **INCONCLUSIVE** = insufficient data / non-simulated segment
- Never use "FAIL" — implies definitive safety failure, but deviations may be operational/acceptable

### Reporting Requirements
**Critical:** Always include:
- Tag number (CDF external_id) for each segment
- Statistical summary only (no process safety interpretation)
- One chart per segment (never combine — pressure ranges differ)
- Acceptance bands visualized on charts (not just pass/fail badge)
