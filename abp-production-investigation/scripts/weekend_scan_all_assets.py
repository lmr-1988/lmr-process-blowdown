"""Cross-asset weekend screening — all 5 Aker BP assets.

Retrieves export-level and PCV data for the weekend (Sat-Sun) and flags
any significant changes.

Usage:  python scripts/weekend_scan_all_assets.py
"""

import sys
sys.path.insert(0, "src")

import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from python_package.cdf_client import create_cdf_client
from python_package.cdf_data import (
    retrieve_timeseries,
    retrieve_timeseries_multi,
    retrieve_timeseries_aggregated,
)
from python_package.enlight_client import fetch_wells, get_well_tags

OSLO = ZoneInfo("Europe/Oslo")
now = datetime.now(OSLO)

# Weekend = Saturday 00:00 to Sunday 23:59 (local)
saturday = (now - timedelta(days=now.weekday() + 2)).replace(hour=0, minute=0, second=0, microsecond=0)
sunday_end = (saturday + timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
baseline_start = saturday - timedelta(hours=12)

print(f"Weekend screening window: {saturday.strftime('%Y-%m-%d %H:%M')} -> {sunday_end.strftime('%Y-%m-%d %H:%M')}")
print(f"Baseline from: {baseline_start.strftime('%Y-%m-%d %H:%M')}")
print("=" * 80)

client = create_cdf_client()

# Export / Platform-level tags
EXPORT_TAGS = {
    "EG Oil Export (Sm3/h)":    "EG_21FI5236B.Y",
    "EG Gas Export (MSm3/d)":   "EG_27.CALC.GrossGasVolume.MSm3d",
    "IA Prod Sep Oil (Sm3/h)":  "IA_21FI3007A.ProcessValue",
    "Skarv Gas Export (MSm3/d)":"SKAP_27FI3100C/Y/PRIM",
    "Skarv Oil Cargo (m3/d)":   "SKAP_20FI0115/Y/PRIM_CALC",
    "Alvheim Oil Export (Sm3/h)":"ALV_21FI5240B.Y",
}

# 1. Export screening
print("\n" + "=" * 80)
print("SECTION 1: EXPORT / PLATFORM-LEVEL SCREENING")
print("=" * 80)

for label, tag in EXPORT_TAGS.items():
    try:
        df = retrieve_timeseries_aggregated(
            client, tag, baseline_start, sunday_end, granularity="1h"
        )
        if df.empty:
            print(f"\n  {label}: NO DATA")
            continue
        col = df.columns[0]
        s = df[col].dropna()
        if s.empty:
            print(f"\n  {label}: ALL NaN")
            continue

        baseline = s[s.index < saturday.strftime('%Y-%m-%d')]
        weekend = s[s.index >= saturday.strftime('%Y-%m-%d')]

        bl_mean = baseline.mean() if not baseline.empty else float('nan')
        wk_mean = weekend.mean() if not weekend.empty else float('nan')
        wk_min = weekend.min() if not weekend.empty else float('nan')
        wk_max = weekend.max() if not weekend.empty else float('nan')
        wk_last = weekend.iloc[-1] if not weekend.empty else float('nan')

        change_pct = ((wk_mean - bl_mean) / bl_mean * 100) if bl_mean else float('nan')

        flag = " *** SIGNIFICANT" if abs(change_pct) > 5 else ""
        print(f"\n  {label}:")
        print(f"    Baseline (Fri PM): {bl_mean:.1f}")
        print(f"    Weekend avg:       {wk_mean:.1f}  (min={wk_min:.1f}, max={wk_max:.1f})")
        print(f"    Last value:        {wk_last:.1f}")
        print(f"    Change vs baseline: {change_pct:+.1f}%{flag}")
    except Exception as e:
        print(f"\n  {label}: ERROR - {e}")


# 2. PCV screening per asset
ASSETS = ["edvardgrieg", "ivaraasen", "skarv", "alvheim", "valhall"]
PCV_THRESHOLD = 2.0

print("\n\n" + "=" * 80)
print("SECTION 2: PCV WELL SCREENING (WEEKEND)")
print("=" * 80)

all_flagged = {}

for asset in ASSETS:
    print(f"\n{'_' * 60}")
    print(f"Asset: {asset.upper()}")
    print(f"{'_' * 60}")

    try:
        wells = fetch_wells(asset)
    except Exception as e:
        print(f"  ERROR fetching wells: {e}")
        continue

    pcv_map = {}
    for w in wells:
        tags = get_well_tags(w)
        pcv_tag = tags.get("PCV", "")
        if pcv_tag:
            pcv_map[w.name] = pcv_tag

    if not pcv_map:
        print(f"  No PCV tags found for {asset}")
        continue

    print(f"  {len(pcv_map)} wells with PCV tags")

    try:
        df = retrieve_timeseries_multi(
            client, list(pcv_map.values()), start=baseline_start, end=sunday_end
        )
    except Exception as e:
        print(f"  ERROR retrieving PCV data: {e}")
        continue

    flagged = []
    for wname in sorted(pcv_map.keys()):
        tag = pcv_map[wname]
        if tag not in df.columns:
            continue
        s = df[tag].resample("10min").mean().dropna()
        if s.empty:
            continue

        baseline = s[s.index < saturday.strftime('%Y-%m-%d')]
        weekend = s[s.index >= saturday.strftime('%Y-%m-%d')]

        bl_mean = baseline.mean() if not baseline.empty else s.iloc[0]
        wk_last = weekend.iloc[-1] if not weekend.empty else float('nan')
        delta = wk_last - bl_mean

        if abs(delta) > PCV_THRESHOLD:
            flagged.append({"well": wname, "baseline": bl_mean, "last": wk_last, "delta": delta})

    if flagged:
        all_flagged[asset] = flagged
        print(f"\n  >>> {len(flagged)} well(s) flagged with PCV change > {PCV_THRESHOLD}%")
    else:
        print(f"\n  All wells stable (no PCV change > {PCV_THRESHOLD}%)")

# 3. Summary
print("\n\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if all_flagged:
    for asset, wells_list in all_flagged.items():
        print(f"\n  {asset.upper()}:")
        for w in wells_list:
            direction = "opened/increased" if w["delta"] > 0 else "choked/closed"
            print(f"    {w['well']}: PCV {w['baseline']:.1f}% -> {w['last']:.1f}% ({w['delta']:+.1f}%) - {direction}")
else:
    print("\n  No significant PCV changes detected on any asset.")

print("\nScreening complete.")
