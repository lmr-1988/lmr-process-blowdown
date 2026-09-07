"""
Retrieve MEASURED topside blowdown pressure curves (per segment) from Cognite
Data Fusion (CDF) for any Aker BP field.

This is the *measured* counterpart to the simulated-curves reader. It pulls the
real pressure-transmitter time series around a blowdown event and returns a clean
time[s] vs pressure[barg] curve per segment.

Data-integrity contract (NON-NEGOTIABLE)
----------------------------------------
* The measured VALUES are never altered. No averaging, smoothing, scaling,
  rounding, interpolation, gap-filling, or server-side aggregation.
* Retrieval is RAW (no CDF aggregates / no granularity) so the depressurisation
  transient is preserved at full resolution.
* The only permitted reduction for EXTREMELY DENSE data is value-preserving
  DECIMATION: selecting a SUBSET of the original measured samples (every datapoint
  kept is an unmodified real measurement). Implemented with LTTB
  (Largest-Triangle-Three-Buckets), which keeps the actual (timestamp, value)
  pairs and preserves the curve shape / peaks. It NEVER invents new values.
* All timestamps are localised to Europe/Oslo (Norway time), never UTC.

CDF access is OAuth interactive (browser login) per the CDF connection guide —
no secrets, read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

OSLO = ZoneInfo("Europe/Oslo")

# Above this many raw samples in the requested window, value-preserving
# decimation kicks in by default. Chosen so a normal blowdown transient keeps
# full fidelity; only pathologically dense pulls get thinned.
DEFAULT_MAX_POINTS = 6000


# --------------------------------------------------------------------------- #
# CDF client (OAuth interactive — browser login, no secrets)                  #
# --------------------------------------------------------------------------- #
def cdf_interactive_client(project: str = "abp"):
    """Instantiate a read-only CogniteClient via browser-based interactive login.

    Mirrors `abp-cdf-connection-guide`. Opens a browser on first call; the token
    caches afterwards. Do NOT use client-credential / secret auth here.
    """
    from cognite.client import ClientConfig, CogniteClient
    from cognite.client.credentials import OAuthInteractive

    TENANT_ID = "3b7e4170-8348-4aa4-bfae-06a3e1867469"
    CLIENT_ID = "779f2b3b-b599-401a-96aa-48bd29132a27"
    CDF_CLUSTER = "az-ams-sp-002"
    SCOPES = [f"https://{CDF_CLUSTER}.cognitedata.com/.default"]
    BASE_URL = f"https://{CDF_CLUSTER}.cognitedata.com"
    AUTHORITY_HOST_URI = "https://login.microsoftonline.com"

    return CogniteClient(
        ClientConfig(
            client_name="Employee",
            project=project,
            base_url=BASE_URL,
            credentials=OAuthInteractive(
                authority_url=f"{AUTHORITY_HOST_URI}/{TENANT_ID}",
                client_id=CLIENT_ID,
                scopes=SCOPES,
            ),
        )
    )


# --------------------------------------------------------------------------- #
# Result container                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class MeasuredCurve:
    """One segment's measured blowdown pressure curve.

    All arrays are aligned and ordered by time. ``pressure`` values are the raw,
    unmodified CDF measurements (or a value-preserving subset of them).
    """

    segment: Optional[str]               # e.g. "BS07" (None if unknown)
    external_id: str                     # CDF time-series external_id
    timestamps: pd.DatetimeIndex         # tz-aware Europe/Oslo
    time_s: np.ndarray                   # seconds from t0 (see t0)
    pressure: np.ndarray                 # barg (raw values, unmodified)
    unit: Optional[str]                  # reported CDF unit, if any
    t0: pd.Timestamp                     # reference time mapped to time_s == 0
    n_raw: int                           # samples returned by CDF in the window
    n_returned: int                      # samples after optional decimation
    thinned: bool                        # True if decimation was applied
    field_meta: dict = field(default_factory=dict)

    @property
    def frame(self) -> pd.DataFrame:
        """Tidy DataFrame indexed by Europe/Oslo timestamp."""
        return pd.DataFrame(
            {"time_s": self.time_s, "pressure_barg": self.pressure},
            index=self.timestamps,
        )


# --------------------------------------------------------------------------- #
# Value-preserving decimation (LTTB) — keeps REAL samples, never averages      #
# --------------------------------------------------------------------------- #
def lttb_indices(x: np.ndarray, y: np.ndarray, n_out: int) -> np.ndarray:
    """Largest-Triangle-Three-Buckets downsampling.

    Returns the INDICES of a subset of the original points to keep. Every kept
    point is an unmodified original sample (no synthetic values). First and last
    points are always kept; the largest-area point in each bucket is selected so
    sharp transitions / peaks survive.
    """
    n = len(x)
    if n_out >= n or n_out < 3:
        return np.arange(n)

    sampled = np.empty(n_out, dtype=np.int64)
    sampled[0] = 0
    bucket_size = (n - 2) / (n_out - 2)
    a = 0
    for i in range(n_out - 2):
        # Average point of the NEXT bucket (the triangle's far vertex).
        avg_start = int(np.floor((i + 1) * bucket_size)) + 1
        avg_end = int(np.floor((i + 2) * bucket_size)) + 1
        avg_end = min(avg_end, n)
        avg_x = x[avg_start:avg_end].mean()
        avg_y = y[avg_start:avg_end].mean()

        # Candidate points in the CURRENT bucket.
        rng_start = int(np.floor(i * bucket_size)) + 1
        rng_end = int(np.floor((i + 1) * bucket_size)) + 1
        xs = x[rng_start:rng_end]
        ys = y[rng_start:rng_end]

        ax, ay = x[a], y[a]
        areas = np.abs((ax - avg_x) * (ys - ay) - (ax - xs) * (avg_y - ay))
        a = rng_start + int(np.argmax(areas))
        sampled[i + 1] = a

    sampled[-1] = n - 1
    return sampled


# --------------------------------------------------------------------------- #
# Retrieval                                                                    #
# --------------------------------------------------------------------------- #
def retrieve_measured_curve(
    client,
    external_id: str,
    start,
    end,
    *,
    segment: Optional[str] = None,
    t0=None,
    max_points: Optional[int] = DEFAULT_MAX_POINTS,
    tz: str = "Europe/Oslo",
) -> MeasuredCurve:
    """Retrieve one segment's measured pressure curve from CDF, raw resolution.

    Parameters
    ----------
    client : CogniteClient
        From :func:`cdf_interactive_client`.
    external_id : str
        Pressure-transmitter time-series external_id (from Enlight or the user).
    start, end : datetime | str
        Event window. Pass tz-aware Europe/Oslo datetimes (recommended) or ISO
        strings. Keep the window tight around the blowdown so the transient is
        not buried in steady-state data.
    segment : str, optional
        Segment label (e.g. "BS07") for bookkeeping only.
    t0 : datetime | str, optional
        Timestamp mapped to ``time_s == 0``. Defaults to the first sample in the
        window. (Choosing BDV-open / decay-start is the evaluator's job — this
        skill just exposes a reference.)
    max_points : int or None
        If the raw window returns more than this many samples, apply
        value-preserving LTTB decimation down to ``max_points``. Set to ``None``
        to disable any thinning and always return every raw sample.
    tz : str
        Output timezone. Defaults to Europe/Oslo.

    Returns
    -------
    MeasuredCurve
    """
    # Convert datetime objects to millisecond timestamps for CDF
    if hasattr(start, 'timestamp'):
        start_ms = int(start.timestamp() * 1000)
    else:
        start_ts = pd.Timestamp(start)
        if start_ts.tz is None:
            start_ts = start_ts.tz_localize(ZoneInfo(tz))
        start_ms = int(start_ts.timestamp() * 1000)
    
    if hasattr(end, 'timestamp'):
        end_ms = int(end.timestamp() * 1000)
    else:
        end_ts = pd.Timestamp(end)
        if end_ts.tz is None:
            end_ts = end_ts.tz_localize(ZoneInfo(tz))
        end_ms = int(end_ts.timestamp() * 1000)
    
    # RAW retrieval — no aggregates, no granularity. Full transient fidelity.
    df = client.time_series.data.retrieve_dataframe(
        external_id=external_id,
        start=start_ms,
        end=end_ms,
    )

    if df is None or df.empty:
        raise ValueError(
            f"No measured data for {external_id!r} in the requested window "
            f"({start} .. {end}). Check the external_id and the event time."
        )

    # CDF SDK returns columns as (NodeId, unit) tuples, not simple external_ids
    # Access the first (and only) column directly via iloc
    if len(df.columns) == 0:
        raise ValueError(
            f"No measured data for {external_id!r} in the requested window "
            f"({start} .. {end}). Check the external_id and the event time."
        )
    
    s = df.iloc[:, 0].dropna()
    if s.empty:
        raise ValueError(
            f"Time series {external_id!r} returned only empty/NaN samples in the "
            f"window. Widen the window or verify the tag."
        )

    # Localise to Norway time. CDF returns tz-naive UTC.
    idx = s.index
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    idx = idx.tz_convert(ZoneInfo(tz))
    s.index = idx
    s = s.sort_index()

    n_raw = len(s)

    # Reference time for the relative seconds axis.
    if t0 is None:
        t0_ts = s.index[0]
    else:
        t0_ts = pd.Timestamp(t0)
        if t0_ts.tz is None:
            t0_ts = t0_ts.tz_localize(ZoneInfo(tz))
        else:
            t0_ts = t0_ts.tz_convert(ZoneInfo(tz))

    timestamps = s.index
    time_s = (timestamps - t0_ts).total_seconds().to_numpy(dtype=float)
    pressure = s.to_numpy(dtype=float)

    # Optional value-preserving decimation for extremely dense pulls.
    thinned = False
    if max_points is not None and n_raw > max_points:
        keep = lttb_indices(time_s, pressure, max_points)
        timestamps = timestamps[keep]
        time_s = time_s[keep]
        pressure = pressure[keep]
        thinned = True

    unit = None
    try:
        meta = client.time_series.retrieve(external_id=external_id)
        unit = getattr(meta, "unit", None)
    except Exception:
        pass

    return MeasuredCurve(
        segment=segment,
        external_id=external_id,
        timestamps=pd.DatetimeIndex(timestamps),
        time_s=time_s,
        pressure=pressure,
        unit=unit,
        t0=t0_ts,
        n_raw=n_raw,
        n_returned=len(pressure),
        thinned=thinned,
    )


def retrieve_measured_curves(
    client,
    mapping: dict,
    start,
    end,
    **kwargs,
) -> dict:
    """Retrieve several segments at once.

    ``mapping`` is ``{segment_id: external_id}``. Returns
    ``{segment_id: MeasuredCurve}``. Segments that error (missing tag / no data)
    are skipped with a printed note rather than aborting the batch.
    """
    out: dict = {}
    for seg, xid in mapping.items():
        try:
            out[seg] = retrieve_measured_curve(
                client, xid, start, end, segment=seg, **kwargs
            )
        except ValueError as exc:
            print(f"  ! {seg} ({xid}): {exc}")
    return out


# --------------------------------------------------------------------------- #
# Optional helper: find candidate pressure tags by name (fallback discovery)   #
# --------------------------------------------------------------------------- #
def search_pressure_tags(client, name: str, limit: int = 10) -> Sequence:
    """Search CDF time series by name (e.g. a segment's PT tag). Discovery only —
    confirm the correct external_id before trusting the curve."""
    return client.time_series.search(name=name, limit=limit)


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Retrieve a measured blowdown pressure curve from CDF (raw, "
        "value-preserving). Prints a summary; never alters the data."
    )
    p.add_argument("external_id", help="CDF pressure-transmitter external_id")
    p.add_argument("start", help="window start (ISO, Norway time, e.g. 2026-05-12T14:25)")
    p.add_argument("end", help="window end (ISO, Norway time)")
    p.add_argument("--segment", default=None, help="segment label, e.g. BS07")
    p.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS,
                   help="value-preserving decimation cap (0 disables)")
    args = p.parse_args()

    max_points = None if args.max_points == 0 else args.max_points

    client = cdf_interactive_client()
    curve = retrieve_measured_curve(
        client,
        args.external_id,
        args.start,
        args.end,
        segment=args.segment,
        max_points=max_points,
    )

    print(f"Segment:     {curve.segment or '-'}")
    print(f"external_id: {curve.external_id}")
    print(f"Unit:        {curve.unit or '?'}")
    print(f"Window:      {curve.timestamps[0]} -> {curve.timestamps[-1]}")
    print(f"t0:          {curve.t0}  (time_s == 0)")
    print(f"Samples:     {curve.n_raw} raw -> {curve.n_returned} returned"
          f"{' (LTTB-thinned, values preserved)' if curve.thinned else ''}")
    print(f"Pressure:    {curve.pressure[0]:.3g} -> {curve.pressure[-1]:.3g} barg "
          f"(min {curve.pressure.min():.3g}, max {curve.pressure.max():.3g})")
