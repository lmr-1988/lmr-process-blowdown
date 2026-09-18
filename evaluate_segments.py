import sys
sys.path.append('.github/skills/blowdown-simulated-curves/scripts')

import pickle
import numpy as np
import pandas as pd
from parse_simulated_curves import load_simulated_curves, fit_exponential, exp_decay

# Load simulated curves and get decay constants
print("Loading simulated curves...")
sim_res = load_simulated_curves('raw/Alvheim Simulated Blowdown Curves.xlsx')
fit_bs01 = fit_exponential(sim_res, 'BS01')
fit_bs02 = fit_exponential(sim_res, 'BS02')

print(f"BS01 simulated decay: k={fit_bs01['k']:.6f} /s, τ={fit_bs01['tau']:.1f} s, R²={fit_bs01['r2']:.4f}")
print(f"BS02 simulated decay: k={fit_bs02['k']:.6f} /s, τ={fit_bs02['tau']:.1f} s, R²={fit_bs02['r2']:.4f}")

# Load measured data
print("\nLoading measured data...")
with open('measured_data.pkl', 'rb') as f:
    measured = pickle.load(f)

time_s = measured['time_s']
measured_bs01 = measured['BS01']
measured_bs02 = measured['BS02']

# External IDs (tag numbers) from the mapping file
external_id_bs01 = "ALV_16PST0139/MeasA/PRIM"
external_id_bs02 = "ALV_16PST0239/MeasA/PRIM"

# Build theoretical comparison curves anchored to measured P0
# P_theo(t) = P0_measured * exp(-k_sim * t)
P0_bs01_measured = measured_bs01[0]
P0_bs02_measured = measured_bs02[0]

print(f"\nBS01 measured P0: {P0_bs01_measured:.2f} barg")
print(f"BS02 measured P0: {P0_bs02_measured:.2f} barg")

# Generate theoretical comparison curves
theo_bs01 = exp_decay(time_s, P0_bs01_measured, fit_bs01['k'])
theo_bs02 = exp_decay(time_s, P0_bs02_measured, fit_bs02['k'])

# Acceptance criteria: ±10% of P₀ as absolute pressure band applied to theoretical curve
band_width_bs01 = 0.10 * P0_bs01_measured  # 10% of starting pressure [barg]
band_width_bs02 = 0.10 * P0_bs02_measured  # 10% of starting pressure [barg]

upper_limit_bs01 = theo_bs01 + band_width_bs01
lower_limit_bs01 = theo_bs01 - band_width_bs01
upper_limit_bs02 = theo_bs02 + band_width_bs02
lower_limit_bs02 = theo_bs02 - band_width_bs02

print(f"\nBS01 acceptance band: theoretical ± {band_width_bs01:.2f} barg (10% of P₀)")
print(f"BS02 acceptance band: theoretical ± {band_width_bs02:.2f} barg (10% of P₀)")

# Calculate deviation metrics
deviation_bs01 = measured_bs01 - theo_bs01
deviation_bs02 = measured_bs02 - theo_bs02

rmse_bs01 = np.sqrt(np.mean(deviation_bs01**2))
rmse_bs02 = np.sqrt(np.mean(deviation_bs02**2))
max_dev_bs01 = np.max(np.abs(deviation_bs01))
max_dev_bs02 = np.max(np.abs(deviation_bs02))

print(f"\nBS01 deviation: RMSE={rmse_bs01:.2f} barg, max={max_dev_bs01:.2f} barg")
print(f"BS02 deviation: RMSE={rmse_bs02:.2f} barg, max={max_dev_bs02:.2f} barg")

# Evaluate pass/fail based on ±10% criterion
# The measured curve must stay within ±10% of the theoretical curve throughout

# Check if measured stays within the ±10% bands around the theoretical curve
within_band_bs01 = (measured_bs01 >= lower_limit_bs01) & (measured_bs01 <= upper_limit_bs01)
within_band_bs02 = (measured_bs02 >= lower_limit_bs02) & (measured_bs02 <= upper_limit_bs02)

# Calculate maximum absolute deviation
max_dev_bs01 = np.max(np.abs(deviation_bs01))
max_dev_bs02 = np.max(np.abs(deviation_bs02))

# Express as percentage of P₀ for reporting
max_percent_of_p0_bs01 = (max_dev_bs01 / P0_bs01_measured) * 100
max_percent_of_p0_bs02 = (max_dev_bs02 / P0_bs02_measured) * 100

print(f"\nBS01 max deviation: {max_dev_bs01:.2f} barg ({max_percent_of_p0_bs01:.1f}% of P₀)")
print(f"BS02 max deviation: {max_dev_bs02:.2f} barg ({max_percent_of_p0_bs02:.1f}% of P₀)")

# Pass/Fail determination: measured should stay within ±10% band throughout
pass_bs01 = np.all(within_band_bs01)
pass_bs02 = np.all(within_band_bs02)

print(f"\nBS01: {'PASS' if pass_bs01 else 'FAIL'}")
print(f"BS02: {'PASS' if pass_bs02 else 'FAIL'}")

# Find time to reach key pressures
def time_to_pressure(time, pressure, target):
    """Find first time when pressure falls to or below target."""
    idx = np.where(pressure <= target)[0]
    if len(idx) == 0:
        return None
    return time[idx[0]]

# Time to 50% of P0
t_50_theo_bs01 = time_to_pressure(time_s, theo_bs01, 0.5 * P0_bs01_measured)
t_50_meas_bs01 = time_to_pressure(time_s, measured_bs01, 0.5 * P0_bs01_measured)
t_50_theo_bs02 = time_to_pressure(time_s, theo_bs02, 0.5 * P0_bs02_measured)
t_50_meas_bs02 = time_to_pressure(time_s, measured_bs02, 0.5 * P0_bs02_measured)

print(f"\nTime to 50% of P0:")
print(f"BS01: {t_50_meas_bs01:.1f} s measured vs {t_50_theo_bs01:.1f} s theoretical (Δ={t_50_meas_bs01-t_50_theo_bs01:.1f} s)")
print(f"BS02: {t_50_meas_bs02:.1f} s measured vs {t_50_theo_bs02:.1f} s theoretical (Δ={t_50_meas_bs02-t_50_theo_bs02:.1f} s)")

# Save all results for report generation
results = {
    'time_s': time_s,
    'segments': {
        'BS01': {
            'segment': 'BS01',
            'external_id': external_id_bs01,
            'measured': measured_bs01,
            'theoretical': theo_bs01,
            'P0': P0_bs01_measured,
            'k': fit_bs01['k'],
            'tau': fit_bs01['tau'],
            'r2': fit_bs01['r2'],
            'band_width': band_width_bs01,
            'upper_limit': upper_limit_bs01,
            'lower_limit': lower_limit_bs01,
            'rmse': rmse_bs01,
            'max_dev': max_dev_bs01,
            'max_percent_of_p0': max_percent_of_p0_bs01,
            'pass': pass_bs01,
            't_50_theo': t_50_theo_bs01,
            't_50_meas': t_50_meas_bs01,
        },
        'BS02': {
            'segment': 'BS02',
            'external_id': external_id_bs02,
            'measured': measured_bs02,
            'theoretical': theo_bs02,
            'P0': P0_bs02_measured,
            'k': fit_bs02['k'],
            'tau': fit_bs02['tau'],
            'r2': fit_bs02['r2'],
            'band_width': band_width_bs02,
            'upper_limit': upper_limit_bs02,
            'lower_limit': lower_limit_bs02,
            'rmse': rmse_bs02,
            'max_dev': max_dev_bs02,
            'max_percent_of_p0': max_percent_of_p0_bs02,
            'pass': pass_bs02,
            't_50_theo': t_50_theo_bs02,
            't_50_meas': t_50_meas_bs02,
        },
    },
}

with open('evaluation_results.pkl', 'wb') as f:
    pickle.dump(results, f)

print("\nEvaluation results saved to evaluation_results.pkl")
