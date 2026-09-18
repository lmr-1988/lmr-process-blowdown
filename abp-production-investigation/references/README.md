# Production Investigation — Reference Notes

This directory contains reference material for the abp-production-investigation skill.

## Core Methodology

### Top-Down Investigation Order
```
Export Metering → Test Headers / Manifolds → Individual Wells → Root Cause
   (platform)        (topside MPFMs)          (rates, pressures)   (PCV, GL, reservoir)
```

### Cross-Asset Platform Export Tags

| Asset | Signal | External ID | Unit |
|-------|--------|-------------|------|
| EG | Oil export rate | `EG_21FI5236B.Y` | Sm³/h |
| EG | Gas export rate | `EG_27.CALC.GrossGasVolume.MSm3d` | MSm³/d |
| IA | Prod Sep Oil Rate | `IA_21FI3007A.ProcessValue` | Sm³/h |
| Skarv | Gas export | `SKAP_27FI3100C/Y/PRIM` | MSm³/d |
| Skarv | Oil to cargo | `SKAP_20FI0115/Y/PRIM_CALC` | m³/d |
| Alvheim | Oil export | `ALV_21FI5240B.Y` | Sm³/h |

### Holistic Screening — Multi-Signal Per Well
NEVER screen PCV alone. Every well must be examined through multiple signals:
- PCV (control — what the operator did)
- WHP D/S PCV (response — pressure downstream of choke)
- WHP U/S PWV (response — upstream pressure)
- Oil/Gas/Water Rate (response — actual production)
- BHP/BHT (reservoir — drawdown, buildup)
- GL Rate / GL Choke (control — artificial lift status)

### BANNED Approaches
- PCV-only screening
- Hourly screening with drill-down (always use 10-min)
- Threshold-based flagging
- compare_time_split / compare_before_after
- Batch-process-then-report

### Signal Combination Interpretation

| PCV | WHP | Rate | Meaning |
|-----|-----|------|---------|
| Stepped down | Rose | Dropped | Intentional choke-back |
| Unchanged | Dropping | Dropping | Reservoir decline or flowline constraint |
| → 0% | Declining | → 0 | Well shut in |
| Opened to 100% | Recovering | Recovering | Restart after shutdown |
| Unchanged | Oscillating | Oscillating | Slugging / hydrate / unstable flow |

### Well Test vs Shutdown Classification
| Signal Pattern | Classification |
|---|---|
| PCV choked, PWV stays open, short, restored | Rate/production test |
| PCV closed + PWV closed, short (<24h), staged restart | Integrity/barrier test |
| PCV closed + PWV closed, extended, no restart | Unplanned shutdown or intervention |
