---
name: abp-enlight-connection-guide
description: "Everything an agent needs to connect to the Enlight platform: base URL, available assets, and equipment/instrumentation API."
category: data-platform
environment: [python, requests, pydantic, pandas]
---

# Enlight API — Agent Connection Guide

> **Purpose:** Everything an LLM agent needs to connect to and retrieve data from the Enlight platform at Aker BP. Hand this file to any new agent as a standalone reference.

---

## 1. Prerequisites

```bash
pip install requests pydantic pandas
```

- Python 3.11+
- Aker BP corporate network or VPN (no separate OAuth token needed)
- For time-series data retrieval, you also need CDF access (see `CDF-Connection-Guide.md`)

---

## 2. Environment Parameters

| Parameter | Value |
|-----------|-------|
| **Base URL** | `https://pbulogger.akerbp.com:8443/api/api/` |
| **Auth** | Aker BP corporate network / VPN — no token required |
| **SSL Verification** | `verify=False` (self-signed cert; use `requests.get(..., verify=False)`) |
| **Database parameter** | Field name, lowercase, no spaces/underscores |

### Available Assets (database names)

| Asset | Database Name |
|-------|---------------|
| Edvard Grieg | `edvardgrieg` |
| Ivar Aasen | `ivaraasen` |
| Skarv | `skarv` |
| Alvheim | `alvheim` |
| Valhall | `valhall` |

---

## 3. Architecture — Two-Layer Data Access

Enlight is a **metadata layer** that sits on top of Cognite Data Fusion (CDF):

```
┌─────────────────────────────────┐
│        Enlight REST API         │
│  (pbulogger.akerbp.com:8443)    │
│                                 │
│  Equipment hierarchy            │
│  Instrumentation → external_id  │
│  Well tests / PBU / VLP         │
│  Operating limits               │
└───────────────┬─────────────────┘
                │ external_id
┌───────────────▼─────────────────┐
│     Cognite Data Fusion (CDF)   │
│  (az-ams-sp-002.cognitedata.com)│
│                                 │
│  Actual time-series values      │
│  Asset hierarchy                │
│  Events                         │
└─────────────────────────────────┘
```

**Enlight** tells you *what sensors exist* and gives you the `external_id`.  
**CDF** gives you the *actual data* for those sensors.

---

## 4. Core Data Model

### Hierarchy

```
Field (database)
  └─ Equipment (platform / well / connector / common_denominator)
       ├─ Subtype (e.g., "Gas Lift", "ESP")
       ├─ Instrumentation[]  ← sensors mapped to CDF time series
       │    ├─ name           → "BHP", "WHP", "Gas Injection Rate", etc.
       │    ├─ external_id    → CDF time-series key (e.g., "pi:111581", "EG_13PT5910.Y")
       │    ├─ PI_tag         → historian tag
       │    ├─ type_id        → links to instrument type definition
       │    └─ required       → mandatory for this subtype?
       ├─ Constants[]  ← fixed parameters (reservoir pressure, PI, skin)
       ├─ Relationships (parent[] / children[])
       └─ VLP (Vertical Lift Performance model)
```

### Key Notes

- `well.instrumentation` contains the sensor-to-CDF mapping (use this for tag discovery)
- `well.children` is a different list (relationship-based, may have fewer items)
- Use `well.equipment_id` (not `well.id` — that doesn't exist on the Pydantic model)
- `subtype` from raw API is `{"name": ..., "type_id": ...}`; on Pydantic model it's an object with `.name`

---

## 5. Pydantic Models (Copy-Paste Ready)

```python
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class Subtype(BaseModel):
    name: str
    type_id: int


class Instrumentation(BaseModel):
    name: str
    timeseries_id: Optional[int] = -1
    external_id: Optional[str] = ""
    PI_tag: Optional[str] = ""
    required: bool
    instrument_id: str
    type_id: Optional[int]
    type: Optional[str] = ""
    unit: Optional[str | int] = -1


class Constants(BaseModel):
    name: str
    value: Optional[float] = 0
    timeseries_id: Optional[int] = None
    external_id: Optional[str] = ""
    constant_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    type_id: int = Field(default=2001)
    PI_tag: Optional[str] = None
    unit: Optional[str] = None
    type: Optional[str] = None


class Relationsship(BaseModel):
    equipment_id: str
    name: str
    timeseries_id: int
    external_id: str
    PI_tag: str
    parent_id: Optional[str] = ""
    child_id: Optional[str] = ""


class Position(BaseModel):
    equipment_id: str
    name: str
    x: Optional[float] = None
    y: Optional[float] = None
    x_pos: Optional[float] = 0
    y_pos: Optional[float] = 0
    position_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))


class OutputModel(BaseModel):
    Columns: List[str]


class PVTModel(BaseModel):
    GOR_CGR_Total_GOR: float = Field(alias="(GOR/CGR/Total GOR)")
    WC_WGR: float = Field(alias="(WC/WGR)")
    Gas_Gravity: float = Field(alias="Gas Gravity")
    Oil_Gravity: float = Field(alias="Oil Gravity")
    Top_TVD: float = Field(alias="Top TVD")

    class Config:
        extra = "allow"


class EquipmentItem(BaseModel):
    Type: str
    Label: str
    Rate_Multiplier: float = Field(alias="Rate Multiplier")
    Measured_Depth: Optional[float] = Field(None, alias="Measured Depth (m)")
    Heat_Transfer_Coefficient: Optional[float] = Field(None, alias="Heat Transfer Coefficient (W/m2/K)")
    True_Vertical_Depth: Optional[float] = Field(None, alias="True Vertical Depth (m)")
    Tubing_Inside_Diameter: Optional[float] = Field(None, alias="Tubing Inside Diameter (m)")
    Tubing_Inside_Roughness: Optional[float] = Field(None, alias="Tubing Inside Roughness (m)")


class VariablesModel(BaseModel):
    NUM_VARIABLES: int

    class Config:
        extra = "allow"


class FileInfoModel(BaseModel):
    class Config:
        extra = "allow"


class VLPDataModel(BaseModel):
    Results: Optional[Dict[str, Any]] = None
    Cases: Optional[Dict[str, Any]] = None
    Gauge_Depths: Optional[List[float]] = Field(None, alias="Gauge Depths")
    Output: Optional[OutputModel] = None
    PVT: Optional[PVTModel] = None
    Equipment: Optional[List[EquipmentItem]] = None
    Variables: Optional[VariablesModel] = None
    TBD: Optional[Any] = None
    File_Info: Optional[FileInfoModel] = Field(None, alias="File Info")

    class Config:
        allow_population_by_field_name = True


class Equipment(BaseModel):
    equipment_id: str
    nickname: Optional[str] = Field(default_factory=str)
    name: str
    positions: Optional[list[Position]] = None
    parent: list[Relationsship] = Field(default_factory=list)
    children: list[Relationsship] = Field(default_factory=list)
    instrumentation: list[Instrumentation] = Field(default_factory=list)
    constants: list[Constants] = Field(default_factory=list)
    inactive_positions: Optional[Position] = None
    type: Literal["well", "common_denominator", "connector", "platform", "None"] = "None"
    continuous_flow_monitoring: bool = False
    enabled_test_device: bool = False
    wells: list["Equipment"] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    is_ready: bool = False
    VLP: Optional[VLPDataModel] = None
    templateId: Optional[str] = None


class Well(Equipment):
    subtype: Subtype = Field(default_factory=Subtype)
    licence: Optional[str] = None
    common_denominator: Optional[str | dict] = None
```

---

## 6. API Endpoint Reference

> **Note:** The URL pattern is `{BASE}/{database}/{endpoint}`. The double `/api/` in the base URL is intentional.

### 6.1 Equipment (Asset Hierarchy)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_equipment` | GET | **All equipment** with full hierarchy, instruments, constants, VLP |
| `/{db}/get_equipment_by_id/{id}` | GET | Single equipment by ID |
| `/{db}/get_equipment_names_and_id_as_list` | GET | Lightweight listing (name + ID only) |
| `/{db}/get_equipment_of_subtype/{subtype_id}/{name}` | GET | Filter by subtype |
| `/{db}/get_equipment_parents` | GET | All parent equipment |
| `/{db}/get_equipment_child` | GET | All child equipment |
| `/{db}/get_common_denominators` | GET | Shared measurement points |

### 6.2 Subtypes & Instrumentation Config

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_all_subtypes` | GET | All subtypes for this field |
| `/{db}/get_subtypes/{category}` | GET | By equipment category |
| `/{db}/get_all_instrumentation_with_id/{equip_id}` | GET | **All instruments for a specific well** |
| `/{db}/get_subtype_instrumentation/{subtype_id}` | GET | Template instruments for a subtype |
| `/api/config/instrumentation/instrument-types` | GET | Global instrument type definitions |
| `/api/config/instrumentation/instrument-types/by-subtype/{id}` | GET | Instrument types for a subtype |
| `/api/config/instrumentation/constant-types` | GET | Global constant type definitions |

### 6.3 Time Series (Enlight-Wrapped CDF)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_timeseries_data_with_id` | POST | Single tag data |
| `/{db}/get_timeseries_data_with_ids` | POST | Multiple tags |
| `/{db}/get_synchroneous_timeseries_data_with_ids` | POST | Aligned multi-tag data (same timestamps) |
| `/{db}/get_latest_timeseries_entry` | POST | Latest value |
| `/{db}/search_timeseries_with_query` | POST | Search tags by query string |

### 6.4 Well Tests

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_well_tests` | GET | All well tests |
| `/{db}/get_latest_well_tests` | GET | Most recent tests |
| `/{db}/get_confirmed_well_tests` | GET | Confirmed tests only |
| `/{db}/get_well_tests_with_id/{id}` | GET | Tests for a specific well |

### 6.5 PBU / PTA (Pressure Analysis)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/find_pbu_samples/{equipment_id}` | POST | Detect PBU events |
| `/{db}/get_pbu_samples_from_database/{id}` | GET | PBU data for a well |
| `/{db}/pta/analyze/{equipment_id}` | POST | Run PTA analysis |
| `/{db}/pta/analyses` | GET | All PTA results |
| `/{db}/pta/equipment/{id}/latest` | GET | Latest PTA for a well |

### 6.6 VLP (Vertical Lift Performance)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_vlp_by_id` | GET | Retrieve VLP model |
| `/{db}/calculate_vlp` | POST | Compute VLP curve |
| `/{db}/calculate_vlp_from_well_test` | POST | VLP from well test data |

### 6.7 Limits, Fluids & Other

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/{db}/get_all_limits` | GET | All operating limits |
| `/{db}/get_full_limits/{equipment_id}` | GET | Limits for a well |
| `/{db}/fluids` | GET | All fluid models |
| `/{db}/get_well_history` | GET | Well intervention/event history |
| `/{db}/get_well_potential` | GET | Well potential estimates |
| `/api/health` | GET | API health check |
| `/time` | GET | Server time |

---

## 7. Common Workflows (Copy-Paste Ready)

### 7.1 Fetch All Wells for a Field

```python
import requests

BASE = "https://pbulogger.akerbp.com:8443/api/api"
ASSET = "edvardgrieg"  # lowercase, no spaces

response = requests.get(f"{BASE}/{ASSET}/get_equipment", verify=False)
data = response.json().get("data", [])

wells = [Well(**item) for item in data if item.get("type") == "well"]

for well in wells:
    print(f"{well.name} ({well.equipment_id}) — {well.subtype.name}")
```

### 7.2 Extract CDF Tags from a Well's Instrumentation

```python
def get_well_tags(well: Well) -> dict:
    """Build {instrument_name: external_id} mapping from a well's instrumentation."""
    tags = {}
    for instr in well.instrumentation:
        if instr.external_id:
            tags[instr.name] = instr.external_id
    return tags


# Example usage
for well in wells:
    tags = get_well_tags(well)
    print(f"\n{well.name}:")
    for name, ext_id in tags.items():
        print(f"  {name}: {ext_id}")
```

### 7.3 Fetch a Specific Well by ID

```python
equip_id = "some-equipment-id"
response = requests.get(f"{BASE}/{ASSET}/get_equipment_by_id/{equip_id}", verify=False)
well_data = response.json()
well = Well(**well_data)
```

### 7.4 Get Subtypes for a Field

```python
subtypes = requests.get(f"{BASE}/{ASSET}/get_all_subtypes", verify=False).json()
for s in subtypes:
    print(f"  {s['name']} (type_id={s['type_id']})")
```

### 7.5 Get Instrument Types for a Subtype

```python
subtype_id = 3  # e.g., Gas Lift
instruments = requests.get(
    f"https://pbulogger.akerbp.com:8443/api/config/instrumentation/instrument-types/by-subtype/{subtype_id}",
    verify=False
).json()
for inst in instruments:
    print(f"  {inst['name']} ({inst.get('unit', 'N/A')})")
```

### 7.6 End-to-End: Enlight → CDF (Discover Tags, Then Fetch Data)

```python
import requests
import pandas as pd
from datetime import datetime, timedelta

# --- Step 1: Get wells from Enlight ---
BASE = "https://pbulogger.akerbp.com:8443/api/api"
ASSET = "edvardgrieg"

response = requests.get(f"{BASE}/{ASSET}/get_equipment", verify=False)
data = response.json().get("data", [])
wells = [Well(**item) for item in data if item.get("type") == "well"]

# --- Step 2: Pick a well and extract BHP external_id ---
target_well = next(w for w in wells if "A03" in w.name)
bhp_ext_id = None
for instr in target_well.instrumentation:
    if instr.name == "BHP" and instr.external_id:
        bhp_ext_id = instr.external_id
        break

# --- Step 3: Fetch time-series data from CDF ---
# (Requires CDF client — see CDF-Connection-Guide.md)
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import OAuthInteractive

client = cdf_interactive_client()  # From CDF-Connection-Guide.md

df = client.time_series.data.retrieve_dataframe(
    external_id=bhp_ext_id,
    start=datetime(2025, 1, 1),
    end=datetime(2026, 1, 1),
    aggregates="average",
    granularity="1d",
    include_aggregate_name=False,
)
print(df.head())
```

---

## 8. Common Instrument Names

These are the standardised instrument names in Enlight's instrumentation model:

| Instrument Name | Typical Unit | Description |
|----------------|-------------|-------------|
| BHP | bara | Bottomhole pressure |
| WHP (or THP) | bara | Wellhead / tubing-head pressure |
| WHP U/S PWV | bara | WHP upstream of production wing valve |
| WHP D/S PCV | bara | WHP downstream of production choke valve |
| CHP | bara | Casing / annulus head pressure |
| Gas Injection Rate | Sm3/h | Gas lift injection rate |
| Oil Rate | Sm3/h | Oil production rate |
| Water Rate | Sm3/h | Water production rate |
| Gas Rate | Sm3/h | Gas production rate |
| Choke Opening | % | Production choke position |
| Temperature | degC | Wellhead temperature |
| ESP Frequency | Hz | ESP pump speed |

---

## 9. Security Rules

- **Enlight is READ-ONLY for agent use.**
- All `POST/PUT/DELETE` endpoints that create, modify, or delete equipment, well tests, VLP, or limits are **FORBIDDEN**.
- `POST` endpoints that *retrieve* data (time series, search, PBU detection) are permitted.
- Do not modify any data — instruct the user to use the Enlight web UI for changes.

---

## 10. Quick Validation Test

```python
import requests

BASE = "https://pbulogger.akerbp.com:8443/api/api"

# Health check
health = requests.get(f"{BASE}/../health", verify=False)
print(f"Enlight API health: {health.status_code}")

# Fetch equipment count
response = requests.get(f"{BASE}/edvardgrieg/get_equipment", verify=False)
data = response.json().get("data", [])
wells = [w for w in data if w.get("type") == "well"]
print(f"Edvard Grieg wells found: {len(wells)}")
```

---

## 11. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `SSLError` | Self-signed certificate | Use `verify=False` in all requests |
| `ConnectionError` | Not on Aker BP network | Connect to VPN |
| Empty `data` list | Wrong database name | Use lowercase, no spaces (e.g., `edvardgrieg` not `Edvard Grieg`) |
| `external_id` is empty | Instrument not mapped to CDF | Skip — not all instruments have CDF tags |
| `well.id` AttributeError | Wrong field name | Use `well.equipment_id` instead |
