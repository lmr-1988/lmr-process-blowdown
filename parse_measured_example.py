import pandas as pd
import numpy as np

# Parse the measured example data
df = pd.read_excel('raw/Alvheim Measured Example Data.xlsx', sheet_name='Measured Pressure')

# Find the header row (contains segment IDs like BS01, BS02)
header_row_idx = None
for i in range(len(df)):
    row = df.iloc[i].astype(str)
    if 'BS01' in row.values:
        header_row_idx = i
        break

if header_row_idx is None:
    raise ValueError("Could not find segment ID header row")

# Get segment IDs from the header row (skip the first two columns which are labels)
segments = []
for val in df.iloc[header_row_idx, 1:]:
    if pd.notna(val) and str(val).strip().startswith('BS'):
        segments.append(str(val).strip())

print(f"Found segments: {segments}")

# Data starts one row after the header
data_start = header_row_idx + 1
data = df.iloc[data_start:].reset_index(drop=True)

# Time is in the first column
time_s = pd.to_numeric(data.iloc[:, 0], errors='coerce').dropna()
print(f"\nTime range: {time_s.min():.1f} - {time_s.max():.1f} s ({len(time_s)} points)")

# Get measured pressures for BS01 and BS02
measured_bs01 = pd.to_numeric(data.iloc[:len(time_s), 1], errors='coerce').values
measured_bs02 = pd.to_numeric(data.iloc[:len(time_s), 2], errors='coerce').values

print(f"\nBS01 measured:")
print(f"  P0: {measured_bs01[0]:.2f} barg")
print(f"  P_final: {measured_bs01[-1]:.2f} barg")

print(f"\nBS02 measured:")
print(f"  P0: {measured_bs02[0]:.2f} barg")
print(f"  P_final: {measured_bs02[-1]:.2f} barg")

# Save for next step
result = {
    'time_s': time_s.values,
    'BS01': measured_bs01,
    'BS02': measured_bs02,
}

import pickle
with open('measured_data.pkl', 'wb') as f:
    pickle.dump(result, f)
    
print("\nMeasured data saved to measured_data.pkl")
