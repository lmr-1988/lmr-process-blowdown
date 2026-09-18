import sys
sys.path.append('.github/skills/blowdown-simulated-curves/scripts')

from parse_simulated_curves import load_simulated_curves, fit_exponential

res = load_simulated_curves('raw/Alvheim Simulated Blowdown Curves.xlsx')

print(f"BS01 - P0: {res.initial_pressure['BS01']:.2f} barg")
print(f"BS02 - P0: {res.initial_pressure['BS02']:.2f} barg")

fit1 = fit_exponential(res, 'BS01')
fit2 = fit_exponential(res, 'BS02')

print(f"\nBS01 - k={fit1['k']:.6f} /s, tau={fit1['tau']:.1f} s, R²={fit1['r2']:.4f}")
print(f"BS02 - k={fit2['k']:.6f} /s, tau={fit2['tau']:.1f} s, R²={fit2['r2']:.4f}")
