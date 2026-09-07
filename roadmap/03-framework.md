# 03 · Framework & Architecture

## Layered view

```
┌──────────────────────────────────────────────────────────────────────┐
│  PRESENTATION                                                        │
│  app.py · frontend/landing.py · frontend/globe.py · frontend/theme.py│
│  Six tabs: Home · Nowcast · 3D Network · Data · Model · Register     │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│  DECISION                                                            │
│  predictor.py      probability, bound by a feature contract          │
│  consistency.py    cross-check against physical evidence             │
│  llm_alert.py      bulletin generation                               │
│  metrics.py        POD · FAR · CSI · HSS · Brier · ROC · reliability │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│  ANALYSIS                                                            │
│  features.py       88 named features in 5 groups                     │
│  optical_flow.py   Farneback motion · advection · cell tracking      │
│  calibration.py    counts to Kelvin · physical thresholds            │
│  geo.py            geostationary projection to EPSG:4326             │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────────────┐
│  INGESTION            utils/datasources/                             │
│  fusion.py     concurrent fetch, merge, provenance                   │
│  mosdac.py     INSAT-3DS / 3DR      radar.py    IMD Doppler          │
│  lightning.py  strike networks      nwp.py      convective params    │
│  surface.py    station observations boundaries.py  ISRO Bhuvan       │
│  base.py       SourceResult · SourceStatus · cache · retry           │
└──────────────────────────────────────────────────────────────────────┘
```

Dependencies point downward only. Ingestion knows nothing about the model;
the model knows nothing about the dashboard.

---

## The three structures that hold it together

### `SourceResult` — provenance on every payload

Defined in `utils/datasources/base.py`. Every data source returns one.

```python
@dataclass
class SourceResult:
    source: str            # "INSAT-3DS TIR-1 (10.8 um)"
    status: SourceStatus   # live | cached | stale | simulated |
                           # unavailable | needs_credentials
    data: Any
    valid_time: str        # observation time, not fetch time
    message: str
    citation: str
    latency_ms: float
```

The key property is `is_observation`, true only for `live`, `cached` and
`stale`. **Simulated data can never be presented as an observation**, and the
dashboard renders the status next to the data.

This exists because the earlier version of this project generated random
blobs and captioned them "Latest IR Image". Provenance is now structural
rather than a matter of remembering.

### `FeatureContract` — the model's binding agreement

Defined in `utils/predictor.py`. Persisted with every model.

```python
@dataclass
class FeatureContract:
    names: List[str]     # exact ordered feature names
    means: List[float]   # training distribution, per feature
    stds:  List[float]
    mins:  List[float]
    maxs:  List[float]
```

Two guarantees:

1. **`align()` looks features up by NAME**, so caller ordering is irrelevant
   and a column-order mismatch is impossible.
2. **`out_of_range()` flags inputs far outside the training distribution**, so
   extrapolation is visible rather than silent.

`load_model()` refuses any model saved without a contract.

### `ModelCard` — honest provenance for the model

```python
@dataclass
class ModelCard:
    training_data: str    # synthetic | observed | mixed
    n_samples: int
    split_strategy: str   # temporal | random | none
    label_definition: str
    validation: Dict      # the full verification report
```

`training_data` drives the banner shown above every number in the UI. A model
fitted to synthetic labels is labelled a demonstration everywhere it appears,
including in the alert text.

---

## Module reference

### `config.py`
Single source of truth for thresholds, endpoints, the satellite fleet, the
36-site Doppler radar network and 28 cities. No magic numbers elsewhere.

Physical thresholds are in **Kelvin**:
`BT_CONVECTIVE_K = 241`, `BT_DEEP_CONVECTIVE_K = 221`, `BT_OVERSHOOT_K = 205`.

### `utils/geo.py`
The geostationary (GEOS) projection, following the CGMS formulation. Locates
the Earth disk by largest connected component plus a least-squares circle fit
to the limb, then resamples the full disk onto a latitude/longitude grid.

Validated against the graticule printed in the source product: the 10°, 20°
and 30° parallels land within 0.03–0.07°.

### `utils/calibration.py`
Converts 8-bit browse values to brightness temperature in Kelvin exactly once,
at ingestion. Also tracks the saturated fraction, because a browse image clips
at the cold end and the retrieved minimum is then a floor, not a measurement.

### `utils/optical_flow.py`
Farneback dense optical flow on a contrast-normalised field, semi-Lagrangian
advection, storm-cell tracking, and an explicit persistence baseline.

Lead times are specified in **hours** and converted using the real frame
interval, so a 30-minute cadence cannot silently halve the horizon.

### `utils/features.py`
`FEATURE_NAMES` is the canonical ordered list — 88 features in five groups.
`build_features()` returns a **named mapping**, never a bare array.

### `utils/predictor.py`
Gradient-boosted classifier with class-imbalance weighting, a temporal
train/test split, and the contract and card described above.

### `utils/metrics.py`
The 2×2 contingency table and everything derived from it, plus Brier score,
Brier skill score, ROC (exact, by the Mann-Whitney rank identity) and
reliability curves.

### `utils/consistency.py`
Cross-examines the model probability against independent physical evidence and
reports the gap. Built after a live run showed 88% HIGH risk beside
"negligible instability".

### `utils/datasources/fusion.py`
Fetches all sources concurrently, merges into one named feature mapping, and
reports which legs were real. Every leg contributes an `*_observed` indicator
so the model can distinguish "no lightning detected" from "lightning not
measured".

---

## Design decisions worth defending

**Features by name, never by position.** Positional arrays are the single most
common source of silent ML bugs. This project makes the failure loud.

**Provenance is a type, not a convention.** Because `SourceStatus` is part of
the return type, a source cannot forget to declare itself.

**Unobserved is not zero.** A missing channel is marked unobserved and carries
an explicit indicator, rather than being zero-filled and treated as a
measurement of absence.

**Physics is retained alongside the model.** Convective indices are not just
features; they are also an independent check on the model's answer.

**The baseline is always present.** Skill is reported relative to persistence,
because a nowcast that cannot beat "assume nothing changes" has no value.

**Degrade, do not fail.** A warning system that disappears when one endpoint
is down is worse than one that continues with a stated confidence note.
