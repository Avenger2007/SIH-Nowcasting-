# Thunderstorm & Lightning Nowcasting (0–6 h)

**SIH 2026 · Problem Statement 26072 · Ministry of Earth Sciences / India Meteorological Department**

AI/ML nowcasting of thunderstorms and lightning from multiple radars, satellite,
lightning and model data.

```bash
pip install -r requirements.txt
streamlit run app.py
```

No API keys are required. Live INSAT-3DS imagery, IMD Doppler radar and NWP
convective parameters all work out of the box.

---

## What actually runs

| Leg (from the problem statement) | Source | Credentials | Status |
|---|---|---|---|
| **Satellite** | INSAT-3DS / 3DR via the public MOSDAC gallery — IR1, IR2, WV, VIS, MIR | none | **live** |
| **Multiple radars** | IMD Doppler Weather Radar composites from `mausam.imd.gov.in` | none | **live** (see caveat) |
| **Model data** | CAPE, CIN, Lifted Index, shear, precipitable water via Open-Meteo (GFS/ECMWF) | none | **live** |
| **Lightning** | Local archive adapter, Blitzortung adapter | institutional | **adapter ready, no feed** |
| Surface | OpenWeatherMap, with NWP analysis fallback | optional key | **live via fallback** |

Every payload carries an explicit status — `live`, `cached`, `stale`,
`simulated`, `unavailable` or `needs_credentials` — and the dashboard displays
it. **Simulated data can never be presented as an observation.**

---

## Honest status

This is the part worth reading before the pitch.

**The pipeline is real and works end to end.** It fetches genuine INSAT
imagery, decodes genuine IMD radar reflectivity, pulls genuine NWP convective
parameters, computes cloud motion, extracts 88 features and produces a
calibrated probability with full verification machinery.

**The model is not yet skilful.** It is fitted to *synthetic* labels, because
no observed lightning archive is connected yet. The dashboard says so in a
banner above every number, the model card records it, and the alert text is
prefixed `[DEMONSTRATION — not an operational forecast]`.

Turning this into a genuine forecast system needs one thing: observed lightning
labels. `scripts/train_real.py` is written and waiting for them.

We think a working pipeline with an honest label about its limits is a far
stronger submission than a claimed 99% accuracy that collapses under the first
question. The engineering register in the dashboard lists all 32 tracked issues,
open ones included.

---

## Architecture

```
INSAT-3DS/3DR         IMD DWR              Lightning network        NWP (GFS)
public gallery        caz/ppz/ppv          IITM / ENTLN / Blitz     Open-Meteo
     │                    │                        │                    │
     └────────────────────┴────────────────────────┴────────────────────┘
                                     │
                        utils/datasources/fusion.py
              concurrent fetch · provenance per leg · named features
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
  optical_flow.py              features.py                 calibration.py
  Farneback motion             88 named features           counts → Kelvin
  Lagrangian advection         5 source groups             physical thresholds
        │                            │                            │
        └────────────────────────────┼────────────────────────────┘
                                     │
                            predictor.py
              XGBoost + FeatureContract (aligned BY NAME) + ModelCard
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
   metrics.py                consistency.py                 llm_alert.py
   POD/FAR/CSI/HSS           model vs physics               template first,
   Brier · ROC · reliability  cross-check                   LLM rephrases only
```

---

## The two decisions that matter

### 1. Features are aligned by name, never by position

The model persists a `FeatureContract`: the ordered feature names *plus* the
training distribution of each. At inference, features are looked up **by name**,
so caller ordering is irrelevant, and a model saved without a contract is
**refused at load time** rather than silently scoring the wrong columns.

The contract also flags inputs far outside the training range. On a real run it
immediately caught 12 features sitting more than 6σ out — which is exactly the
failure that made the previous model's output meaningless.

### 2. Verification uses the contingency table, not accuracy

Thunderstorms are rare. A model that always says "no storm" scores 95% accuracy
and is useless. `utils/metrics.py` reports POD, FAR, CSI, frequency bias, HSS,
PSS, Brier score, Brier skill score, ROC AUC and reliability curves — against a
**temporal** split and a **persistence baseline**, because skill only means
anything relative to "assume nothing changes".

---

## Physical consistency check

The model's probability is cross-checked against independent physical evidence
(CAPE, CIN, Lifted Index, cloud-top temperature, radar reflectivity, lightning
rate, diurnal timing). When they disagree, the dashboard says so and shows which
evidence points which way.

This was built after a real run showed 88% HIGH risk while the NWP panel
directly beneath it said "negligible instability, strong capping inversion". Both
numbers were correct; they simply disagreed. A system that flags its own
contradiction is defensible. One that displays it without noticing is not.

---

## Layout

```
app.py                     Single dashboard (5 tabs)
config.py                  Thresholds, endpoints, satellite & radar network
ISSUES.json                Engineering register, rendered live in the UI

utils/
  calibration.py           8-bit counts ↔ Kelvin; physical thresholds
  geo.py                   Geostationary projection; full disk → EPSG:4326
  features.py              88 named features in 5 source groups
  optical_flow.py          Farneback motion, advection, cell tracking
  predictor.py             FeatureContract, ModelCard, XGBoost
  metrics.py               POD/FAR/CSI/HSS/Brier/ROC/reliability
  consistency.py           Model-versus-physics cross-check
  llm_alert.py             Template alerts; optional LLM rephrasing
  datasources/
    base.py                SourceResult, SourceStatus, cache, retry
    mosdac.py              INSAT-3DS/3DR + rolling frame buffer
    radar.py               IMD DWR, legend-driven dBZ decoding
    lightning.py           Strike features, labels, archive adapter
    nwp.py                 Convective parameters
    surface.py             Surface observations
    fusion.py              Concurrent multi-source fusion
    boundaries.py          Official boundaries from ISRO Bhuvan (NRSC)

frontend/
  globe.py                 three.js network globe
  theme.py                 Design tokens

scripts/
  live_test.py             End-to-end smoke test against live sources
  collect_frames.py        Build the INSAT frame buffer (for motion)
  train_real.py            Train on observed lightning labels

tests/test_pipeline.py     56 tests; regression tests name the bug they guard
```

---

## Running things

```bash
# Dashboard
streamlit run app.py

# Prove the pipeline works against live sources
python scripts/live_test.py Delhi

# Build the frame buffer so cloud motion becomes available
python scripts/collect_frames.py --watch --interval 900

# Tests (offline by default)
pytest
pytest -m live        # include live-network tests
```

**Before a demo, start the frame collector.** MOSDAC publishes only the newest
scan, so optical flow needs at least two distinct scans buffered. Run the
collector for an hour beforehand and motion will be live.

---

## Official boundaries and georeferencing

Two things had to be right before any boundary could be drawn.

### The boundary source is ISRO Bhuvan, deliberately

India's official external boundary differs from the de-facto lines shown by
international datasets. **Natural Earth, OpenStreetMap, GADM and most Western
basemaps depict the Line of Control**, not the boundary the Government of India
recognises. Using one of those in a submission to the Ministry of Earth
Sciences would be a serious unforced error.

Every boundary in this project therefore comes from **ISRO Bhuvan**, the
national geoportal run by the National Remote Sensing Centre, Department of
Space — which carries the Survey of India depiction.

```
https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms
  basemap:STATE_BDY_UPD    state boundaries, updated
  basemap:india_state_ql   states, filled (globe texture)
  basemap:INDIA_DIST       district boundaries
```

Verified current: Ladakh appears as a Union Territory distinct from Jammu &
Kashmir, reflecting the 2019 reorganisation.

If Bhuvan is unreachable, **no boundary is drawn at all**. The code has no
fallback to a foreign dataset, and `test_boundary_failure_does_not_fall_back_to_foreign_data`
enforces that.

### Imagery is properly georeferenced

A boundary is only meaningful over correctly located pixels. The earlier build
cut India out of the INSAT full disk using fixed pixel fractions, which is not
georeferenced at all.

`utils/geo.py` now implements the standard geostationary (GEOS) projection, so
the full disk is resampled onto a real EPSG:4326 grid. Two bugs had to be fixed
to get there, both caught by validation rather than luck:

- the Earth-disk detector was including MOSDAC's bright title bar, throwing the
  fitted centre out by ~140 px (`BUG-029`);
- the scan-angle sign followed the raw CGMS listing, which assumes a
  south-first scan and silently flipped the image, so the "India" crop was
  actually returning southern Indian Ocean (`BUG-030`).

**Validation:** after reprojection, the graticule burned into the source
product lands within **0.03–0.07°** of the true 10°, 20° and 30° parallels —
sub-pixel at INSAT's 4 km resolution. That check does not depend on the
boundary overlay, so it cannot be fooled by a pretty picture.

---

## Known limitations

Listed in full in the dashboard's Engineering register. The ones that matter:

- **No observed training labels yet.** The headline limitation. `ISSUE-021`.
- **Only 3 of 37 DWR sites publish public products** (Delhi, Goa, Jot), so the
  "multi-radar" composite usually has one contributing radar. `ISSUE-022`.
- **Satellite brightness temperature is uncalibrated.** The public gallery
  serves rendered JPEGs; Kelvin is inferred from an assumed display stretch, and
  the scene saturates at the cold end. A free MOSDAC account fixes this.
  `ISSUE-023`.

---

## Attribution

Satellite imagery ISRO / MOSDAC. Radar products India Meteorological Department.
NWP data Open-Meteo (GFS / ECMWF IFS, CC-BY 4.0). Built for Smart India
Hackathon 2026, problem statement 26072.
