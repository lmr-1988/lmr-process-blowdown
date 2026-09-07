---
name: blowdown-performance-evaluator
description: Status rules for comparing measured and simulated topside blowdown curves.
---

# Blowdown Performance Evaluator

Use the user-supplied blowdown initiation time as `t = 0`, compare measured pressure with the simulated-rate comparison curve, and apply the segment acceptance criterion supplied by the user.

## Low starting pressure rule

If the measured starting pressure is **below 3 barg**, classify the segment as **`ALREADY DEPRESSURISED`**. Do not issue PASS or REVIEW for that segment and do not assess it against the normal curve-deviation criterion. Show the status with a **light-green** badge (`#b7e4c7` with dark-green text `#1b4332`) in reports.

This status means the segment was already depressurised at the supplied event start time; it is not a judgement of valve or blowdown performance.
