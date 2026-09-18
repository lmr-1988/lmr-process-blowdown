import sys
sys.path.append('.github/skills/blowdown-measured-curves/scripts')

import pandas as pd
from zoneinfo import ZoneInfo
from retrieve_measured_curves import cdf_interactive_client, retrieve_measured_curves

# Blowdown initiation time (Europe/Oslo)
start = pd.Timestamp("2026-01-11T17:51:06", tz=ZoneInfo("Europe/Oslo"))
end = pd.Timestamp("2026-01-11T18:21:06", tz=ZoneInfo("Europe/Oslo"))  # 30 minutes later

# Segment to external_id mapping for Alvheim
mapping = {
    "BS01": "ALV_16PST0139/MeasA/PRIM",
    "BS02": "ALV_16PST0239/MeasA/PRIM",
}

print("Connecting to CDF (browser login)...")
client = cdf_interactive_client()

print(f"\nRetrieving measured curves from {start} to {end} (Europe/Oslo)...")
curves = retrieve_measured_curves(
    client,
    mapping,
    start=start,
    end=end,
    t0=start,  # Set t=0 at the blowdown initiation time
)

for seg, curve in curves.items():
    print(f"\n{seg}:")
    print(f"  External ID: {curve.external_id}")
    print(f"  P0 (at t=0): {curve.pressure[0]:.2f} {curve.unit or 'barg'}")
    print(f"  P_final: {curve.pressure[-1]:.2f} {curve.unit or 'barg'}")
    print(f"  Samples: {curve.n_raw} raw -> {curve.n_returned} returned")
    print(f"  Thinned: {curve.thinned}")
    print(f"  Duration: {curve.time_s[-1]:.1f} s")
