<div align="center">

# Nowcasting thunderstorms before they strike

**0–6 hour thunderstorm and lightning prediction for India, from live satellite, radar and model data.**

[![Problem Statement](https://img.shields.io/badge/SIH_2026-SIH26072-1273D4?style=flat-square)](roadmap/01-problem-statement.md)
[![Ministry](https://img.shields.io/badge/MoES-India_Meteorological_Department-0B4F94?style=flat-square)](https://mausam.imd.gov.in)
[![Tests](https://img.shields.io/badge/tests-68_passing-1E8E52?style=flat-square)](tests/test_pipeline.py)
[![Python](https://img.shields.io/badge/python-3.10+-4C4BC7?style=flat-square)](https://python.org)
[![No GPU](https://img.shields.io/badge/hardware-CPU_only-E8890C?style=flat-square)](#)

</div>

---

```bash
pip install -r requirements.txt
streamlit run app.py
```

**No API keys required.** Live INSAT-3DS imagery, IMD Doppler radar and
numerical model data all work out of the box.

---

## What this is

Lightning kills more people in India each year than floods or cyclones. The
deaths follow a pattern: outdoors, in rural districts, during the afternoon,
among farmers and outdoor workers. District-wide alerts issued hours ahead do
not help someone who has forty minutes to reach shelter.

This system fuses four live data sources into a 0–6 hour thunderstorm and
lightning probability for any Indian city, and — as much as anything else in
this repository — it is careful about telling you how much to trust the answer.

| Data leg (named in the problem statement) | Source | Credentials | Status |
|---|---|---|---|
| **Satellite** | INSAT-3DS / 3DR via the MOSDAC public gallery — IR1, IR2, WV, VIS, MIR | none | **Live** |
| **Multiple radars** | IMD Doppler Weather Radar composites | none | **Live** |
| **Model data** | CAPE, CIN, Lifted Index, shear, precipitable water | none | **Live** |
| **Lightning** | Adapters for archive, Blitzortung, IITM/ENTLN | institutional | Ready, awaiting data |

---

## Honest status

**The pipeline is real.** It fetches genuine INSAT imagery from ISRO,
georeferences it through the geostationary projection, decodes genuine IMD
radar reflectivity, pulls genuine convective parameters, measures cloud motion
from consecutive scans, and runs a complete verification suite.

**The model is not yet skilful.** It is fitted to *synthetic* labels, because
no observed lightning archive is connected yet. Every screen says so — a
banner above every number, a field on the model card, and a prefix on the
alert text.

Connecting one lightning archive is the single remaining step.
[`scripts/train_real.py`](scripts/train_real.py) is written and waiting for it.

> A working pipeline with an honest label is a stronger position than a
> claimed accuracy figure that collapses under the first question.

---

## What makes it different

### Provenance is part of the data type

Every payload carries a status — `live`, `cached`, `stale`, `simulated`,
`unavailable`, `needs_credentials` — and the dashboard renders it beside the
data. **Simulated data can never be presented as an observation.** This is
enforced structurally, not by convention.

### Features are bound by name, never by position

The model persists a **feature contract**: ordered names plus the training
distribution of each. Inference aligns by name, so caller ordering is
irrelevant, and a model saved without a contract is refused at load. The
contract also flags inputs far outside the training range — on a live run it
immediately caught 12 features beyond 6σ.

### Accuracy is banned

With a 5% storm rate, always answering "no storm" scores 95% accuracy and
catches nothing. This project reports POD, FAR, **CSI**, HSS, Brier skill
score, ROC and reliability — against a **temporal** split and a **persistence
baseline**. A test asserts the trap explicitly.

### The model is cross-examined against the physics

The probability is checked against independent evidence — CAPE, CIN, Lifted
Index, cloud-top temperature, radar reflectivity, lightning rate, diurnal
timing. When they disagree, the dashboard says so and shows which evidence
points which way.

This was built after a live run showed 88% HIGH risk while the panel directly
beneath read *"negligible instability, strong capping inversion"*. Both numbers
were correct; they simply disagreed. A system that flags its own contradiction
is defensible; one that displays it without noticing is not.

### Boundaries come from ISRO Bhuvan, deliberately

Natural Earth, OpenStreetMap and GADM depict the Line of Control rather than
the boundary the Government of India recognises. All boundaries here come from
**ISRO Bhuvan** (National Remote Sensing Centre, Department of Space), which
carries the Survey of India depiction. If Bhuvan is unreachable, **no boundary
is drawn** — a test prevents anyone adding a foreign fallback.

---

## The pipeline

```
INSAT-3DS/3DR        IMD Doppler radar      Lightning network      NWP model
MOSDAC gallery       caz / ppz / ppv        IITM / ENTLN           CAPE · CIN · LI
     │                     │                      │                     │
     └─────────────────────┴──────────────────────┴─────────────────────┘
                                    │
                         concurrent fetch · provenance per leg
                                    │
     ┌──────────────────────────────┼──────────────────────────────┐
     │                              │                              │
  geo.py                     optical_flow.py                 features.py
  geostationary →            Farneback motion                88 named features
  EPSG:4326                  Lagrangian advection            5 source groups
     │                              │                              │
     └──────────────────────────────┼──────────────────────────────┘
                                    │
                              predictor.py
                  gradient boosting + FeatureContract + ModelCard
                                    │
     ┌──────────────────────────────┼──────────────────────────────┐
     │                              │                              │
 metrics.py                  consistency.py                  llm_alert.py
 POD·FAR·CSI·HSS             model vs physics                bulletin
 Brier · ROC                 cross-check                     (template first)
```

---

## Georeferencing, and why it took two attempts

A boundary drawn over pixels cropped by fixed fractions is decoration. So the
INSAT full disk is resampled through the standard geostationary (GEOS)
projection onto a real EPSG:4326 grid.

Two bugs surfaced getting there, both caught by validation rather than luck:

- **The Earth-disk detector was eating MOSDAC's title bar.** The bright header
  and colour wedge pulled the fitted centre up ~140 px and inflated the radius.
- **The projection was vertically flipped.** The raw CGMS scan-angle sign
  assumes a south-first scan; INSAT imagery is north-up. The "India" crop was
  returning southern Indian Ocean — and it was *not* obvious, because the
  boundary overlay drawn on top still looked like India.

**Validation now does not rely on the overlay.** After reprojection, the
graticule burned into the source product lands within **0.03–0.07°** of the
true 10°, 20° and 30° parallels — sub-pixel at INSAT's 4 km resolution.

---

## Documentation

Full documentation is in [`roadmap/`](roadmap/README.md).

| | | |
|---|---|---|
| [Problem statement](roadmap/01-problem-statement.md) | [Setup](roadmap/02-setup.md) | [Framework](roadmap/03-framework.md) |
| [Workflow](roadmap/04-workflow.md) | [Data sources](roadmap/05-data-sources.md) | [The science](roadmap/06-science.md) |
| [Verification](roadmap/07-verification.md) | [Model roadmap](roadmap/08-model-roadmap.md) | [Deployment](roadmap/09-deployment.md) |
| [Presentation](roadmap/10-presentation.md) | [Demo script](roadmap/11-demo-script.md) | [Q&A prep](roadmap/12-qa-preparation.md) |

---

## Running it

```bash
# Dashboard
streamlit run app.py

# Prove the pipeline against live sources
python scripts/live_test.py Delhi

# Build the frame buffer so cloud motion becomes available
python scripts/collect_frames.py --watch --interval 900

# Tests
pytest                # 63 offline
pytest -m live        # 5 against live endpoints
```

**Before a demonstration, start the frame collector.** MOSDAC publishes only
the newest scan, so optical flow needs at least two distinct scans buffered.
Run it for an hour beforehand and cloud motion will be live.

---

## Layout

```
app.py                     Dashboard — six tabs
config.py                  Thresholds, endpoints, satellite and radar network
ISSUES.json                Engineering register, rendered live in the UI

utils/
  geo.py                   Geostationary projection → EPSG:4326
  calibration.py           8-bit counts ↔ Kelvin, physical thresholds
  features.py              88 named features across 5 source groups
  optical_flow.py          Farneback motion, advection, cell tracking
  predictor.py             FeatureContract, ModelCard, gradient boosting
  metrics.py               POD / FAR / CSI / HSS / Brier / ROC / reliability
  consistency.py           Model-versus-physics cross-check
  llm_alert.py             Bulletin generation
  datasources/
    base.py                SourceResult, SourceStatus, cache, retry
    mosdac.py              INSAT-3DS / 3DR + rolling frame buffer
    radar.py               IMD Doppler, legend-driven dBZ decoding
    lightning.py           Strike features, forward-looking labels
    nwp.py                 Convective parameters
    surface.py             Surface observations
    boundaries.py          Official boundaries from ISRO Bhuvan
    fusion.py              Concurrent multi-source fusion

frontend/
  landing.py               Home page
  globe.py                 3D observation-network globe
  theme.py                 Design system

scripts/
  live_test.py             End-to-end smoke test against live sources
  collect_frames.py        INSAT frame buffer collector
  train_real.py            Training on observed lightning labels

roadmap/                   Full documentation
tests/test_pipeline.py     68 tests; regression tests name the bug they guard
```

---

## Engineering register

**41 issues tracked · 37 resolved · 4 open with documented next steps.**

Every resolved bug has a regression test named after it. The register is
rendered live inside the dashboard, open items included — including the bugs
we found in our own work, such as an integer overflow that made radar decode
terrain as 40 dBZ echo, and the projection sign error above.

---

## Known limitations

- **No observed training labels yet.** The headline limitation.
- **Only 3 of 36 Doppler sites publish public products** (Delhi, Goa, Jot), so
  the multi-radar composite usually has one contributing radar.
- **Satellite brightness temperature is uncalibrated.** The public gallery
  serves rendered JPEGs; Kelvin is inferred from an assumed stretch and the
  scene saturates at the cold end. A free MOSDAC account fixes this.
- **Parallax is not corrected.** Tall clouds appear displaced by tens of
  kilometres near the domain edges.
- **Output is a point forecast, not a grid.** Gridded output is the largest
  remaining gain in operational value.

All of these, with next steps, are in
[roadmap/08-model-roadmap.md](roadmap/08-model-roadmap.md).

---

## Attribution

Satellite imagery: **ISRO / MOSDAC**, INSAT-3DS and INSAT-3DR IMAGER.
Radar products: **India Meteorological Department**, mausam.imd.gov.in.
Administrative boundaries: **ISRO Bhuvan / National Remote Sensing Centre**,
Department of Space — Survey of India depiction.
Numerical model data: **Open-Meteo** (GFS / ECMWF IFS), CC-BY 4.0.

Built for **Smart India Hackathon 2026**, problem statement **SIH26072**,
Ministry of Earth Sciences / India Meteorological Department.
