---
name: abp-cdf-connection-guide
description: "Everything an agent needs to connect to Cognite Data Fusion: OAuth interactive flow, environment parameters, and data retrieval patterns."
category: data-platform
environment: [python, cognite-sdk, pandas]
---

# Cognite Data Fusion (CDF) — Agent Connection Guide

> **Purpose:** Everything an LLM agent needs to connect to and retrieve data from Cognite Data Fusion at Aker BP. Hand this file to any new agent as a standalone reference.

---

## 1. Prerequisites

```bash
pip install cognite-sdk pandas
```

- Python 3.11+
- Aker BP corporate network or VPN
- Aker BP Azure AD credentials (browser login will be triggered)

---

## 2. Environment Parameters

| Parameter | Value |
|-----------|-------|
| **Project** | `abp` |
| **CDF Cluster** | `az-ams-sp-002` |
| **Base URL** | `https://az-ams-sp-002.cognitedata.com` |
| **Tenant ID** | `3b7e4170-8348-4aa4-bfae-06a3e1867469` |
| **Client ID** | `779f2b3b-b599-401a-96aa-48bd29132a27` |
| **Auth Flow** | OAuth Interactive (browser-based) |
| **Authority URL** | `https://login.microsoftonline.com/3b7e4170-8348-4aa4-bfae-06a3e1867469` |
| **Scopes** | `["https://az-ams-sp-002.cognitedata.com/.default"]` |

---

## 3. Connection Code (Copy-Paste Ready)

```python
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import OAuthInteractive


def cdf_interactive_client(project: str = "abp") -> CogniteClient:
    """Instantiate a CogniteClient using browser-based interactive login."""

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


# Usage:
client = cdf_interactive_client()  # Opens browser on first call; token caches afterward
```

> **⚠️ IMPORTANT — Do NOT use `OAuthClientCredentials`.** This guide uses **interactive browser login only**. Do not generate code that requires a `CLIENT_SECRET`, `.env` file, or service-account credentials. Individual users authenticate via the browser popup — no secrets are needed. If the user has not provided a client secret, that is expected and correct.

---

## 4. Key CDF Concepts

| Concept | Description |
|---------|-------------|
| **Time series** | Named sensor channels with timestamped values. Identified by `external_id`. |
| **Assets** | Hierarchical equipment tree (field → platform → well → sensor). |
| **Events** | Discrete occurrences (well tests, interventions, shutdowns). |
| **Data sets** | Logical groupings for access control. |
| **Relationships** | Links between assets, time series, and events. |

---

## 5. Data Retrieval Patterns

### 5.1 Retrieve a Single Time Series

```python
df = client.time_series.data.retrieve_dataframe(
    external_id="EG_13PT5910.Y",
    start="2025-01-01",
    end="2025-06-01",
)
```

### 5.2 Retrieve Multiple Tags

```python
tags = [
    "EG_13PT5910.Y",    # WHP U/S PWV
    "EG_13FI1218K.Y",   # Oil Volume Rate SC
    "EG_13FI1225.Y",    # Gas Lift Rate
]

df = client.time_series.data.retrieve_dataframe(
    external_id=tags,
    start="2025-06-01",
    end="2025-06-30",
)
```

### 5.3 Server-Side Aggregation

```python
df = client.time_series.data.retrieve_dataframe(
    external_id="EG_13PT5910.Y",
    start="2025-01-01",
    end="2026-01-01",
    aggregates="average",
    granularity="1h",
    include_aggregate_name=False,
)
```

Available aggregates: `average`, `min`, `max`, `count`, `sum`, `interpolation`, `step_interpolation`, `total_variation`, `continuous_variance`, `discrete_variance`.

Granularity units: `s`, `m`, `h`, `d`, `w`, `mo`, `q`, `y`.

### 5.4 Retrieve Latest Value

```python
result = client.time_series.data.retrieve_latest(external_id="EG_13PT5910.Y")
print(f"Value: {result.value} {result.unit}")
print(f"Time:  {result.timestamp}")
```

> `retrieve_latest()` returns a `LatestDatapoint` object with `.value`, `.unit`, `.timestamp`. It is NOT a list.

### 5.5 Time-Ago Strings (SDK Direct Calls Only)

The SDK accepts time-ago strings for `start`/`end`:

```python
df = client.time_series.data.retrieve_dataframe(
    external_id="EG_13PT5910.Y",
    start="7d-ago",
    end="now",
)
```

Valid formats: `"12h-ago"`, `"2w-ago"`, `"30d-ago"`, `"now"`.

### 5.6 Browse Asset Hierarchy

```python
# Find wells under a platform
wells = client.assets.list(parent_external_ids=["sp_edvard_grieg"], limit=100)
for w in wells:
    print(f"{w.external_id}: {w.name}")

# Find time series for a well
ts_list = client.time_series.list(asset_external_ids=["EG_A03"], limit=50)
for ts in ts_list:
    print(f"  {ts.external_id}: {ts.name} ({ts.unit})")
```

### 5.7 Search Time Series by Name

```python
results = client.time_series.search(name="WHP", limit=10)
for ts in results:
    print(f"{ts.external_id}: {ts.name}")
```

---

## 6. SDK v8 Column Handling

`retrieve_dataframe` returns MultiIndex columns `(external_id, aggregate, unit)` when using aggregates. For raw data, columns are plain `external_id` strings.

```python
# Safe pattern: flatten columns after retrieval
df = client.time_series.data.retrieve_dataframe(
    external_id=["tag_a", "tag_b"],
    aggregates="average",
    granularity="1h",
    include_aggregate_name=False,
)
# Columns are now just external_id strings
```

---

## 7. Timezone Handling

CDF returns timestamps in UTC (tz-naive by default). Always localize to Norway time for user-facing output:

```python
from zoneinfo import ZoneInfo

df.index = df.index.tz_localize("UTC").tz_convert("Europe/Oslo")
```

- April–October = CEST (UTC+2)
- October–March = CET (UTC+1)
- Use `ZoneInfo("Europe/Oslo")`, never hardcode the offset.

---

## 8. External ID Naming Conventions

| Pattern | Example | Meaning |
|---------|---------|---------|
| `EG_13PT####.Y` | `EG_13PT5910.Y` | Edvard Grieg, pressure transmitter, live PV |
| `EG_13PST####.X` | `EG_13PST1221.X` | Pressure switch/transmitter |
| `EG_13FI####.Y` | `EG_13FI1225.Y` | Flow indicator |
| `EG_13TT####.PV` | `EG_13TT5921.PV` | Temperature transmitter, process value |
| `EG_A03.FAS.*` | `EG_A03.FAS.GasVolStdStg1` | Flow Allocation System (calculated, not measured) |
| `ec_edg_well_day_*` | `ec_edg_well_day_prod_alloc_gas_vol_sm3_...` | Daily allocated production |
| `pi:######` | `pi:111581` | Legacy PI historian tag |

---

## 9. Performance Tips

- `limit=None` is fastest (parallel internal fetching).
- Batch multiple time series in one `retrieve_dataframe` call.
- Use `retrieve_arrays()` for large numpy-based queries.
- Use server-side aggregates to reduce data volume when raw resolution isn't needed.

---

## 10. Status Codes & Data Quality

```python
df = client.time_series.data.retrieve_dataframe(
    external_id="EG_13PT5910.Y",
    start="2025-01-01",
    end="2025-02-01",
    include_status=True,
    ignore_bad_datapoints=False,
)
```

---

## 11. Synthetic Time Series

```python
result = client.time_series.data.synthetic.query(
    expressions="A + B",
    variables={"A": "tag_external_id_1", "B": "tag_external_id_2"},
    start="2025-01-01",
    end="2025-02-01",
)
```

---

## 12. Utility Functions

```python
from cognite.client.utils import timestamp_to_ms, ms_to_datetime, datetime_to_ms
```

---

## 13. Security Rules

- **Never hardcode tokens or secrets.** The OAuth Interactive flow handles auth via browser.
- For automated/production pipelines, use OAuth Client Credentials (requires a client secret — obtain from IT).
- Never commit `.env` files or tokens to version control.
- **CDF is read-only for agent use.** Do not create, update, or delete time series, assets, or events.

---

## 14. Quick Validation Test

Run this to confirm your connection works:

```python
client = cdf_interactive_client()
result = client.time_series.data.retrieve_latest(external_id="EG_13PT5910.Y")
print(f"CDF connected. Latest WHP A03: {result.value} {result.unit} at {result.timestamp}")
```

Expected output: a pressure value in `barg` with a recent timestamp.

---

## Boundaries

- This guide covers **OAuth Interactive (browser-based) authentication only**
- Do NOT use `OAuthClientCredentials`, `CLIENT_SECRET`, or `.env` files — those are for automated service accounts and are not covered here
- Do NOT prompt the user for a client secret — interactive login requires no secrets
- Do NOT create, update, or delete CDF resources — agent access is read-only
- For automated pipeline auth, contact IT to obtain service-account credentials separately
