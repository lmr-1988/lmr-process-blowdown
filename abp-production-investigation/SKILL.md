---
name: abp-production-investigation
description: Investigate production changes on Aker BP oil & gas assets (Edvard Grieg, Ivar Aasen, Skarv, Alvheim, Valhall) using a top-down "zoom lens" methodology — start at platform export, drill into headers, then individual wells using holistic multi-signal screening (PCV + WHP + rates + BHP + gas-lift). Use whenever the user asks "what happened on [asset]?", "why did rate drop?", "screen the weekend", or any cross-asset production-event question. The agent IS the screening logic — no thresholds, no batch automation.
category: data-analysis
environment: [python, cognite-sdk, pandas]
---

# Aker BP — Production Change Investigation

## Purpose

Investigate production changes on Aker BP oil & gas assets using a top-down “zoom lens” methodology. Mirrors how a PE engineer thinks: export → headers → wells → root cause. The agent IS the screening logic — no hardcoded thresholds, no batch automation.

## When to Use

- “What happened on [asset] this weekend?”
- “Why did rate drop on Edvard Grieg?”
- “Screen the weekend for all assets”
- Any cross-asset production-event question
- Rate drop / well shutdown / unexpected behaviour investigation

## Requirements

- CDF access with authenticated `CogniteClient` (see `abp-cdf-connection-guide` for setup, `abp-cdf-data-retrieval` for usage patterns)
- Asset knowledge loaded (see `abp-asset-*` skills)
- Enlight API access for well inventory (see `abp-enlight-connection-guide`)

The mandatory methodology for any production-change question.

## Core Principle: Top-Down, Downstream First

```
Platform Export Metering  →  Headers / Manifolds  →  Individual Wells  →  Root Cause
```

**Never** start with individual well anomalies and work upward. That buries the lede.

## Zoom Lens — 4 Stages

### 1. Wide shot — Platform export (always first)

Pull platform-level export tags at **10-min** resolution for the window.

| Asset | Tag(s) |
|-------|--------|
| EG | Oil `EG_21FI5236B.Y` (~540 Sm³/h), Gas `EG_27.CALC.GrossGasVolume.MSm3d` (~0.28 MSm³/d) |
| IA | Oil `IA_21FI3007A.ProcessValue` (~215 Sm³/h, NOT in Enlight — hardcode) |
| Skarv | Oil-to-cargo `SKAP_20FI0115/Y/PRIM_CALC` (calculated, watch artifacts), Gas `SKAP_27FI3100C/Y/PRIM` |
| Alvheim | No reliable export tag — go straight to PCV+WHP per well |
| Valhall | No rate tags at all — PCV positions as proxy |

Question: "Did total production change? When? By how much?"

### 2. Medium shot — Headers / manifolds / well groups

If export changed, isolate the affected section.

- EG: per-well MPFM on A-slot producers
- Solveig (B-wells): shared subsea flowline
- IA: D-wells share test-separator routing
- Skarv: 5 templates (A / BC / Idun / Tilje / Ærfugl)
- Valhall: 5 platforms (B / G / N / S / V)

### 3. Close-up — Individual wells (HOLISTIC, multi-signal)

Read **all available signals** per well at 10-min:

- **PCV** (control — what the operator did)
- **WHP D/S PCV** (response — pressure downstream)
- **WHP U/S PWV** (response — wellbore condition)
- **Oil / Gas / Water Rate** (response — actual production, where MPFM exists)
- **BHP / BHT** (reservoir — drawdown / buildup, temperature)
- **GL Rate / GL Choke** (control — artificial lift)
- **Annulus Pressure** (integrity — casing / barrier)

Cross-reference control vs response. PCV change with no WHP/rate response is a different event from PCV change with rate collapse. Stable PCV but declining WHP/rate is a reservoir/flowline issue invisible to PCV-only screening.

### 4. Context zoom — Time perspective

Is this new or recurring? Did neighbouring wells respond simultaneously (facility) or independently (well)? Is the well trending or stepping?

## MANDATORY Rules

### Default window: 36 h (not 24 h)

"Last 24 hours" means 24 h of changes WITH context. Always retrieve at least 36 h so the first 12 h is baseline. Extend to 48–72 h if a change is near the start of the window.

### Default granularity: 10 min — NEVER 1 h

`retrieve_timeseries_aggregated()` defaults to `1h` — always override to `10m`. Hourly destroys 30-min outages, slug cycles (10–20 min), sharp choke steps, and pressure spikes.

### Reactive tool use — small iterative steps

```
RETRIEVE → READ → REASON (share with user) → DECIDE NEXT → RETRIEVE → ...
```

Never run a big monolithic script that retrieves everything and dumps results. The user must see the thought process between each retrieval.

### Cross-asset queries: FULL DEPTH PER ASSET

When asked about "all AkerBP assets":
- Run the same full holistic investigation on each asset (EG, IA, Skarv, Alvheim, Valhall)
- Same depth as a single-asset investigation — never slim down
- Process sequentially, share findings between assets
- Read the per-asset facts skill (`abp-asset-*`) before each asset

## BANNED Approaches

- **PCV-only screening** — misses response failures and reservoir-driven issues
- **Hourly screening + drill-down** — wasteful two-pass; hourly hides transients
- **Threshold flagging** (`if abs(delta) > 2.0: flag`) — blind to context
- **`compare_time_split` / `compare_before_after`** — mean-based, averages away short events
- **Batch-process-then-report** — bottom-up automation, not engineering analysis

## Agent Reasoning IS the Screening Logic

There are no hardcoded thresholds. The agent:

1. **Reads** the 10-min profile per well (visual inspection of values, not just stats)
2. **Recognises shapes**: steps, ramps, spikes, oscillations, flatlines, gaps
3. **Cross-references**: PCV changed → did WHP respond? PCV stable → but WHP dropping?
4. **Considers context**: absolute magnitude, well history, neighbours, asset knowledge
5. **Explains**: "B6 PCV stepped 45→100% Sat 01:30, WHP recovered 28→42 bara — restart."

## Well Change Classification

| Class | Source | Look for |
|-------|--------|----------|
| Intended | Operator moved a control valve (PCV, GL choke, topside choke) | Control signal change matching rate response |
| Unintended (well-intrinsic) | Slugging, water breakthrough, wax/scale, sand, gas coning | WHP, BHP, temperatures, watercut trend |
| Unintended (back-pressure) | Neighbour startup raises manifold P → rates fall on others | Simultaneous WHP rise + rate decline across multiple wells |
| Unintended (facility) | Separator trip, pump stop, header P change | All wells on header respond simultaneously |
| Subtle | Model mismatch (FAS vs MPFM), gradual drift | Compare modelled vs measured; multi-day pressure trends |

## Common Patterns

| Pattern | Likely Cause | Next Step |
|---------|--------------|-----------|
| All wells decline simultaneously | Facility event | Check facility tags |
| One well rate drops, PCV unchanged | Reservoir / wellbore | WHP, BHP trends |
| One well rate drops, PCV reduced | Deliberate choke-back | Did PCV recover? |
| Multiple subsea wells decline + one started | Back-pressure | Check total flowline rate (see `abp-subsea-back-pressure`) |
| PCV → 0 briefly, then reopened | Well test or GLV test | Duration + reopen level |
| WHP rising, rate declining | Wax / hydrate / back-pressure | Pipeline pressures |
| PCV changed, no response | Well dead / DHSV closed | Valve status |

## Pre-Flight Checklist

Before every investigation:

1. Load asset facts (`abp-asset-edvard-grieg`, etc.)
2. `wells = fetch_wells(asset)` (cached) — via the Enlight API (see `abp-enlight-connection-guide`)
3. Identify export tags (table above)
4. Start at export, then zoom in
5. Convert rates to **Sm³/d** (×24 from CDF Sm³/h)
6. All timestamps in **Europe/Oslo (Norway time)**, never UTC

## Reporting

When producing a written report or HTML output, follow the same top-down structure: Export → Headers → Wells → Root Cause. See `abp-html-reporting` for branded HTML output.

## Package Contents

- `scripts/` — Investigation automation scripts.
- `references/README.md` — Investigation reference: top-down methodology, cross-asset export tags, holistic screening, BANNED approaches, signal combination interpretation matrix.

## Boundaries

This skill intentionally excludes:

- Automated threshold-based anomaly detection
- PBU analysis (see `abp-pressure-buildup-analysis`)
- Slugging detection and characterisation (see `abp-slugging-analysis`)
- CDF authentication or data retrieval patterns (see `abp-cdf-data-retrieval`)
- Report formatting (see `abp-html-reporting` or `abp-pdf-reporting`)

## Source Notes
- `knowledge/pcv-screening-pattern.md`
- `knowledge/whp-bhp-screening-method.md`
- `knowledge/signal-availability-inventory-method.md`
- `knowledge/well-test-vs-shutdown-classification.md`
- `knowledge/cross-asset-screening-tags.md`
- `knowledge/agent-coding-pitfalls.md`
