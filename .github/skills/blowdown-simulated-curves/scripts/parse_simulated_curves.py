"""
Parse an Aker BP "Simulated Blowdown Curves" Excel workbook into tidy curves.

Field-agnostic: works for any field's workbook (the file name identifies the
field, e.g. "Alvheim/Skarv/Edvard Grieg Simulated Blowdown Curves.xlsx"). The
segment set, time range and step are read from whichever workbook is passed; do
not assume one field's numbers apply to another.

Canonical layout (verified against `raw/Alvheim Simulated Blowdown Curves.xlsx`,
sheet "Simulated blowdown curves"; other fields follow the same shape):

    row 0 : title            -> "Simulated Blowdown"
    row 1 : note             -> e.g. "Low pressure, not simulated (BS21-BS24)"
    row 2 : axis labels      -> A:"Time [s]"  B:"Pressure [barg]"
    row 3 : segment IDs      -> B..:  BS01, BS02, ... BSnn
    row 4+: data             -> A: time [s], B..: pressure [barg]

Known gotchas this parser handles:
  * Header is offset (segment IDs in row index 3, data from row index 4).
  * A "-" cell means the segment was NOT simulated (low pressure) -> dropped.
  * Below the last populated time row, the sheet contains trailing rows with a
    BLANK time column. These are a solver/steady-state artifact (a segment can
    jump discontinuously there, e.g. BS35 11.26 -> 0.047) and are NOT part of the
    plottable curve. Only rows with a valid numeric time are kept.

Inviolable rules enforced here:
  * The curve values are returned EXACTLY as stored in the workbook. The parser
    never smooths, scales, rounds, resamples, interpolates, or fills the curve.
    The only transform is `to_numeric`, which maps the "-" sentinel to NaN so a
    non-simulated segment can be detected and dropped.
  * Nothing after the last populated timestep is read or returned. The data
    region ends at the last row with a valid numeric time.

Usage:
    from parse_simulated_curves import load_simulated_curves
    res = load_simulated_curves(r"raw/Alvheim Simulated Blowdown Curves.xlsx")
    res.time_s            # ndarray of seconds, 0..1800
    res.curves            # dict[str, ndarray]  e.g. res.curves["BS07"]
    res.frame             # tidy DataFrame: time_s + one column per simulated segment
    res.not_simulated     # list of segment IDs that were "-"
"""

from __future__ import annotations

import os
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class SimulatedCurves:
    frame: pd.DataFrame                       # time_s + one column per simulated segment (barg)
    time_s: np.ndarray                        # time axis in seconds
    curves: Dict[str, np.ndarray]             # segment_id -> pressure[barg] array
    segments: List[str]                       # simulated segment IDs (in sheet order)
    not_simulated: List[str] = field(default_factory=list)  # segments that were "-"
    initial_pressure: Dict[str, float] = field(default_factory=dict)  # P at t=0 [barg]
    final_pressure: Dict[str, float] = field(default_factory=dict)    # P at last t [barg]
    sheet_name: str = ""
    dt_s: Optional[float] = None              # nominal timestep [s] if uniform


def _find_header_row(raw: pd.DataFrame) -> int:
    """Locate the row holding the segment IDs (cells like 'BS01')."""
    for i in range(min(10, len(raw))):
        row = raw.iloc[i].astype(str)
        if row.str.match(r"^\s*BS\d{1,3}\s*$", case=False).sum() >= 3:
            return i
    raise ValueError("Could not locate the segment-ID header row (expected cells like 'BS01').")


def load_simulated_curves(
    path: str,
    sheet_name: str = "Simulated blowdown curves",
    use_cache: bool = True,
) -> SimulatedCurves:
    """Load and clean a simulated blowdown curves workbook into tidy curves.
    
    Parameters
    ----------
    path : str
        Path to the Excel workbook
    sheet_name : str
        Sheet name to read
    use_cache : bool
        If True, use cached parsed data if available and fresh
    """
    # Check cache
    if use_cache:
        cache_dir = Path("raw/.cache")
        cache_dir.mkdir(exist_ok=True)
        cache_file = cache_dir / f"{Path(path).stem}_parsed.pkl"
        
        if cache_file.exists():
            # Check if cache is newer than source Excel
            cache_mtime = cache_file.stat().st_mtime
            source_mtime = Path(path).stat().st_mtime
            
            if cache_mtime > source_mtime:
                # Cache is fresh, load it
                try:
                    with open(cache_file, 'rb') as f:
                        return pickle.load(f)
                except Exception:
                    pass  # Fall through to re-parse
    
    # Parse from Excel. Workbook exports vary in capitalization, so accept a
    # case-insensitive match while preserving the actual worksheet name.
    workbook = pd.ExcelFile(path)
    sheet_lookup = {name.casefold(): name for name in workbook.sheet_names}
    actual_sheet_name = sheet_lookup.get(sheet_name.casefold())
    if actual_sheet_name is None:
        blowdown_sheets = [name for name in workbook.sheet_names
                           if "blowdown" in name.casefold()]
        if len(blowdown_sheets) == 1:
            actual_sheet_name = blowdown_sheets[0]
        else:
            raise ValueError(
                f"Worksheet {sheet_name!r} not found in {path!r}. "
                f"Available sheets: {workbook.sheet_names}"
            )
    raw = pd.read_excel(workbook, sheet_name=actual_sheet_name, header=None)

    hdr = _find_header_row(raw)
    seg_ids = [str(x).strip() for x in raw.iloc[hdr, 1:].tolist()]

    # Time axis lives in column 0 from the row after the header onward.
    time_all = pd.to_numeric(raw.iloc[hdr + 1:, 0], errors="coerce")

    # GOTCHA: trust only rows where time is populated. Trailing rows with a blank
    # time column are a solver/steady-state artifact, not part of the curve.
    last = time_all.last_valid_index()
    if last is None:
        raise ValueError("No numeric time values found in the time column.")
    data = raw.loc[hdr + 1:last, :]

    time_s = pd.to_numeric(data.iloc[:, 0], errors="coerce").to_numpy()

    simulated: List[str] = []
    not_simulated: List[str] = []
    curves: Dict[str, np.ndarray] = {}
    for offset, seg in enumerate(seg_ids, start=1):
        col = pd.to_numeric(data.iloc[:, offset], errors="coerce")  # "-" -> NaN
        if col.notna().sum() == 0:
            not_simulated.append(seg)
            continue
        simulated.append(seg)
        curves[seg] = col.to_numpy()

    frame = pd.DataFrame({"time_s": time_s})
    for seg in simulated:
        frame[seg] = curves[seg]

    diffs = np.diff(time_s)
    dt = float(diffs[0]) if len(diffs) and np.allclose(diffs, diffs[0]) else None

    result = SimulatedCurves(
        frame=frame,
        time_s=time_s,
        curves=curves,
        segments=simulated,
        not_simulated=not_simulated,
        initial_pressure={s: float(curves[s][0]) for s in simulated},
        final_pressure={s: float(curves[s][-1]) for s in simulated},
        sheet_name=actual_sheet_name,
        dt_s=dt,
    )
    
    # Save to cache
    if use_cache:
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(result, f)
        except Exception:
            pass  # Non-fatal if cache save fails
    
    return result


def time_to_pressure(res: SimulatedCurves, segment: str, target_barg: float) -> Optional[float]:
    """First time [s] at which the simulated curve for `segment` falls to <= target_barg.

    Returns None if the curve never reaches the target within the simulated window.
    Uses linear interpolation between the bracketing samples for sub-step accuracy.
    """
    if segment not in res.curves:
        raise KeyError(f"{segment!r} is not a simulated segment. Simulated: {res.segments}")
    p = res.curves[segment]
    t = res.time_s
    if p[0] <= target_barg:
        return float(t[0])
    for i in range(1, len(p)):
        if p[i] <= target_barg:
            p0, p1 = p[i - 1], p[i]
            t0, t1 = t[i - 1], t[i]
            if p1 == p0:
                return float(t1)
            return float(t0 + (t1 - t0) * (p0 - target_barg) / (p0 - p1))
    return None


# ---------------------------------------------------------------------------
# Analytical model
#
# The simulated blowdown curves are first-order exponential pressure decay:
#
#       P(t) = P0 * exp(-k * t)            [P0 in barg, k in 1/s, t in s]
#
# equivalently P(t) = P0 * exp(-t / tau) with tau = 1 / k (the time constant in
# seconds; the time to fall to 1/e ~= 37% of P0). This holds while the blowdown
# valve orifice is choked (sonic), which is the case for the high-pressure part
# of every segment. Fitting all simulated segments gives R^2 >= ~0.99.
#
# IMPORTANT: this model is for analysis / reporting only. It NEVER replaces or
# alters the stored simulated curve, which is always used exactly as in the
# workbook.
# ---------------------------------------------------------------------------

def exp_decay(t, P0: float, k: float):
    """First-order exponential pressure decay: P(t) = P0 * exp(-k * t)."""
    return P0 * np.exp(-np.asarray(t, dtype=float) * k)


def fit_exponential(res: "SimulatedCurves", segment: str) -> Dict[str, float]:
    """Fit P(t) = P0 * exp(-k * t) to one simulated segment.

    Returns a dict with the fitted parameters and goodness-of-fit:
        P0   : fitted initial pressure [barg]
        k    : rate constant [1/s]
        tau  : time constant 1/k [s]
        r2   : coefficient of determination
        t_half : time to reach 50% of P0  = ln(2) / k  [s]

    Requires scipy. Does not modify the stored curve.
    """
    from scipy.optimize import curve_fit  # local import; scipy is optional

    if segment not in res.curves:
        raise KeyError(f"{segment!r} is not a simulated segment. Simulated: {res.segments}")
    t = res.time_s.astype(float)
    y = res.curves[segment].astype(float)
    p0_guess = res.initial_pressure[segment]
    (P0f, k), _ = curve_fit(
        exp_decay, t, y, p0=[p0_guess, 1.0 / 200.0],
        bounds=([0.0, 1e-9], [1e4, 1e3]), maxfev=200000,
    )
    yhat = exp_decay(t, P0f, k)
    ss_res = float(np.sum((y - yhat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return {
        "P0": float(P0f),
        "k": float(k),
        "tau": float(1.0 / k),
        "r2": r2,
        "t_half": float(np.log(2.0) / k),
    }


if __name__ == "__main__":
    import glob
    import sys

    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        # Auto-discover a field workbook in raw/ (ignore Excel lock files ~$*).
        candidates = [p for p in glob.glob("raw/*Simulated Blowdown Curves*.xlsx")
                      if "~$" not in p]
        if not candidates:
            sys.exit("No 'raw/*Simulated Blowdown Curves*.xlsx' workbook found. "
                     "Pass a path, e.g. python parse_simulated_curves.py "
                     "'raw/<Field> Simulated Blowdown Curves.xlsx'")
        src = candidates[0]
        if len(candidates) > 1:
            print(f"Multiple workbooks found; using {src!r}. Others: "
                  f"{[c for c in candidates if c != src]}\n")

    res = load_simulated_curves(src)
    print(f"File:  {src!r}")
    print(f"Sheet: {res.sheet_name!r}")
    print(f"Time:  {res.time_s[0]:.0f} -> {res.time_s[-1]:.0f} s "
          f"({len(res.time_s)} pts, dt={res.dt_s} s)")
    print(f"Simulated segments ({len(res.segments)}): {', '.join(res.segments)}")
    print(f"Not simulated ({len(res.not_simulated)}): {', '.join(res.not_simulated) or '-'}")

    try:
        print("\nModel  P(t) = P0 * exp(-k * t)   (tau = 1/k)")
        print(f"\n{'seg':6} {'P0[barg]':>9} {'Pend':>9} {'k[1/s]':>10} {'tau[s]':>8} {'R2':>7}")
        for s in res.segments:
            fit = fit_exponential(res, s)
            print(f"{s:6} {res.initial_pressure[s]:9.3g} {res.final_pressure[s]:9.3g} "
                  f"{fit['k']:10.5f} {fit['tau']:8.1f} {fit['r2']:7.4f}")
    except ImportError:
        print("\n(scipy not available — skipping exponential fit; pass --with scipy)")
        print("\nseg     P0[barg]   Pend[barg]   t->50%[s]")
        for s in res.segments:
            p0 = res.initial_pressure[s]
            thalf = time_to_pressure(res, s, 0.5 * p0)
            thalf_str = f"{thalf:8.1f}" if thalf is not None else "    n/a "
            print(f"{s:6}  {p0:8.3g}   {res.final_pressure[s]:9.3g}   {thalf_str}")
