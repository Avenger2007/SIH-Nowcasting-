# 08 · Model Roadmap — what remains

What still has to be done for the model to work as well as this problem
deserves, in priority order. Each item states why it matters, what to do, and
roughly what it costs.

---

## Priority table

| # | Task | Impact | Effort | Blocked by |
|---|---|---|---|---|
| 1 | Observed lightning labels | **Decisive** | 1–2 weeks | Institutional data access |
| 2 | Multi-season frame archive | **Decisive** | Ongoing, automated | Time |
| 3 | Calibrated L1B satellite data | High | 3–4 days | Free MOSDAC account |
| 4 | Gridded output instead of a point | High | 1–2 weeks | Nothing |
| 5 | Probability calibration | High | 2 days | Task 1 |
| 6 | Full radar network access | Medium-high | 1 week | IMD institutional access |
| 7 | Lead-time-specific models | Medium | 3–4 days | Task 1 |
| 8 | Convective initiation | Medium | 2–3 weeks | Tasks 1, 2 |
| 9 | Parallax correction | Medium | 2 days | Nothing |
| 10 | Deep learning on the archive | Medium | 3–4 weeks | Tasks 1, 2 |
| 11 | Ensemble and uncertainty | Low-medium | 1 week | Task 1 |
| 12 | Sounder vertical profiles | Low-medium | 1 week | Task 3 |

---

## 1 · Observed lightning labels — the one that matters

**This is the single blocking item.** Everything else is refinement.

The model is currently fitted to labels generated from a formula. It has
learned that formula, not the atmosphere. No amount of feature engineering,
architecture work or hyperparameter tuning changes that.

**What is needed:** a lightning strike archive covering at least one full
pre-monsoon and monsoon season (March–September) over the region of interest,
as `time, lat, lon` records.

**Sources, in order of preference**

| Source | Route |
|---|---|
| IITM/ISRO lightning network | Institutional request through the college, citing SIH participation |
| IMD | The problem statement's own department — they hold ENTLN/GLD360 subscriptions |
| Earth Networks ENTLN | Commercial; sometimes offers academic access |
| Blitzortung | Community network; contributor account gives raw stroke data |

**How to use it once obtained**

```bash
# 1. Drop the archive in
cp lightning_2026.csv data/lightning/     # columns: time,lat,lon[,type]

# 2. Collect satellite frames over the same period
python scripts/collect_frames.py --watch --interval 900

# 3. Train against observed labels
python scripts/train_real.py --city Delhi --lead 3 --radius 25
```

`scripts/train_real.py` is already written. It builds the forward-looking
label, enforces a temporal split, computes a persistence baseline, and reports
CSI skill relative to it. The model card will then read
`training_data: observed`, and every "DEMONSTRATION" banner in the UI
disappears automatically.

**Expected outcome:** a real CSI, probably 0.25–0.45 at 1–3 hour lead. Modest
and genuine beats large and unreproducible.

---

## 2 · Multi-season frame archive

One storm season is roughly 4,300 INSAT scans at 30-minute cadence. With a
positive rate near 5%, that is around 200 positive samples per location —
thin, but workable when pooled across many locations.

**Two ways to build it**

- **Forward:** run `scripts/collect_frames.py --watch` continuously from now.
  Costs nothing but time. Start immediately; it accumulates while other work
  proceeds.
- **Backward:** order historical L1B from MOSDAC. Faster to a usable dataset,
  and the reason a MOSDAC account is worth having.

**Pool across locations.** Training per-city wastes data. Sampling many points
across India multiplies the dataset and forces the model to learn
generalisable physics rather than the local climatology of one city.

---

## 3 · Calibrated L1B satellite data

Public browse imagery is a rendered 8-bit JPEG. Brightness temperature is
inferred from an assumed display stretch, and the scene saturates at the cold
end — exactly where deep convection lives.

The result is that `bt_min` currently reports a **floor**, not a measurement,
and thresholds near 205 K are unreliable.

L1B NetCDF from the MOSDAC Order API carries true calibrated Kelvin plus a
geolocation grid, which also removes the need to fit the Earth disk.

**Cost:** a free account at `mosdac.gov.in/signup`, 1–2 day approval, plus a
few days to wire the asynchronous FTP order workflow.

---

## 4 · Gridded output instead of a single point

Currently the system produces one probability for one city. An operational
nowcast should produce a **map** — a probability field on a grid.

This is the largest change in user-facing value. It turns "Delhi: 65%" into
"here is where the storms will be in two hours", which is what a district
disaster management officer actually needs.

**Approach:** the feature extraction already works on rasters. Instead of
reducing to scalars for one point, evaluate the model per grid cell over a
coarse grid (say 0.25°, about 25 km). Satellite and radar features are already
spatial; NWP fields can be fetched on a grid; only the lightning features need
a neighbourhood aggregation per cell.

**Watch out for:** inference cost. 32 × 32 cells is 1,024 model calls per
run — fine for gradient-boosted trees, and it should be batched.

---

## 5 · Probability calibration

A model can rank well and still be badly calibrated — saying 80% when the true
frequency is 40%. For a warning system this matters more than ranking, because
thresholds are set on the probability.

Once trained on real labels, fit **isotonic regression** or **Platt scaling**
on a held-out calibration split and verify with the reliability curve already
implemented in `utils/metrics.py`.

---

## 6 · Full radar network access

Only 3 of 36 sites publish public products, so the multi-radar composite
usually has one contributing radar. The problem statement explicitly says
*multiple radars*.

Institutional access to IMD Level-II volume data would give:
- all operational sites rather than three;
- true dBZ instead of a palette inversion;
- full volume scans, enabling **echo top height** and **VIL** (vertically
  integrated liquid), both strong severe-weather predictors;
- radial velocity for rotation detection.

Worth requesting explicitly as part of SIH participation, since IMD is the
department that set the problem.

---

## 7 · Lead-time-specific models

A single model predicting "storm within 0–6 hours" blurs two different
problems. At 30 minutes, extrapolation dominates. At 6 hours, the environment
dominates and current cloud position is nearly irrelevant.

Train separate models per lead band — 0–1 h, 1–3 h, 3–6 h — and expect the
feature importance to shift from satellite and motion features toward CAPE,
shear and diurnal terms as lead time grows. That shift is also a good sanity
check that the model has learned real structure.

---

## 8 · Convective initiation

Tracking existing storms is largely solved by optical flow. Predicting where
**new** storms form in currently clear air is the hard, valuable problem.

Signals to add:
- **Cumulus field detection** in the visible and mid-IR channels — small
  cumulus fields often precede deep convection by 1–2 hours;
- **Boundary detection** — outflow boundaries and sea breeze fronts are
  visible as thin arc-shaped lines and are classic initiation triggers;
- **Terrain forcing** — elevation and slope as static features; the Western
  Ghats and Himalayan foothills initiate reliably;
- **Moisture convergence** in the boundary layer from model fields.

---

## 9 · Parallax correction

A 15 km-tall cloud viewed obliquely from geostationary orbit appears displaced
from its true ground position — tens of kilometres near the edges of the
Indian domain, and increasing with latitude.

Cloud-top height is already retrieved in `utils/calibration.py`, and the
projection maths in `utils/geo.py` provides the viewing geometry. The
correction is a modest addition and improves alignment between satellite
features, radar echoes and lightning strikes — which matters directly for
label quality.

---

## 10 · Deep learning, once the archive exists

With one to two seasons of gridded data, deep models become defensible:

- **ConvLSTM / PredRNN** for spatiotemporal extrapolation;
- **U-Net** mapping a stack of recent frames to a future lightning probability
  field;
- **Optical flow as an auxiliary input** rather than a replacement — the
  physics-based motion field is a strong prior.

Deliberately **not** done now. A deep model trained on synthetic labels would
be indefensible, and the gradient-boosted baseline must be beaten before
anything more complex is justified.

---

## 11 · Ensemble and uncertainty

A single probability hides how confident the system is. Options:
- quantile or bootstrap ensembles over the gradient-boosted model;
- multi-model NWP input (GFS and ECMWF separately) to expose environmental
  spread;
- report a confidence interval alongside the probability.

The `SourceResult` provenance already gives partial uncertainty information —
a nowcast with 2 of 4 legs live is inherently less certain, and the UI says so.

---

## 12 · Sounder vertical profiles

INSAT carries a 19-channel sounder giving retrieved temperature and humidity
profiles. Currently only imager channels are used.

Sounder-derived instability would be a genuinely satellite-based CAPE
estimate, independent of the numerical model — valuable because it observes
the atmosphere rather than simulating it.

---

## Suggested sequence

**Weeks 1–2 — unblock**
Start the frame collector today. Request lightning data from IITM/IMD and a
MOSDAC account in parallel. Both are waiting-on-others tasks, so start them
first.

**Weeks 3–4 — while waiting**
Gridded output (task 4) and parallax correction (task 9). Neither is blocked
by anything.

**On data arrival**
Train on real labels (task 1), calibrate (task 5), split by lead time
(task 7). This is the step that converts the project from a working pipeline
into a skilful forecast system.

**Later**
Convective initiation, deep learning, ensembles.

---

## What to say about this in the presentation

Do not hide it. The strongest framing is:

> The pipeline is real and runs on live government data. The model is
> deliberately labelled as a demonstration because it has not yet been trained
> on observed lightning — and we would rather show you that label than claim a
> skill we cannot evidence. The training script is written; it needs a data
> agreement, not more engineering.

An evaluator who has sat through a dozen inflated accuracy claims will
recognise that as the more competent position.
