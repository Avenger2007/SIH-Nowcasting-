# 01 · The Problem Statement

## As published

| Field | Value |
|---|---|
| **ID** | SIH26072 |
| **Title** | AI/ML based nowcasting of thunderstorm and lightning using atmospheric observation including multiple radars, satellite, lightning and model data |
| **Organisation** | Ministry of Earth Sciences (MoES) |
| **Department** | India Meteorological Department |
| **Category** | Software |
| **Theme** | Disaster Management |

---

## Reading the statement carefully

The title is doing more work than it first appears. Four things are named
explicitly, and a submission that skips any of them has not answered the
question:

1. **multiple radars** — plural. Not one radar image; a composite.
2. **satellite** — the INSAT series is the obvious source for India.
3. **lightning** — both an input and, ultimately, the thing being predicted.
4. **model data** — numerical weather prediction output, not just observations.

Two more requirements are implied rather than stated:

5. **nowcasting**, not forecasting. The accepted definition is 0 to 6 hours.
   This is a different problem from a next-day forecast and needs different
   methods — extrapolation of current observations dominates, and model
   output alone is too coarse in time.
6. **AI/ML**, so the fusion must be learned, not a fixed rule table.

---

## Why this problem exists

Lightning is the deadliest weather hazard in India by number of lives lost —
ahead of floods and cyclones. The deaths have a distinct pattern: they happen
outdoors, in rural districts, during the pre-monsoon and monsoon months,
concentrated among farmers, herders and construction workers.

That pattern matters for system design:

- **The warning must be local.** A district-wide alert covering thousands of
  square kilometres, most of which will see nothing, trains people to ignore
  it.
- **The warning must be early enough to act, and late enough to be right.**
  Reaching shelter takes minutes. A useful warning arrives 30 to 90 minutes
  ahead — squarely inside the nowcasting window.
- **The warning must be understandable.** The audience is not meteorologists.
  A probability alone is not actionable; it needs a risk level, a time window
  and a concrete instruction.

---

## What makes it technically hard

**Thunderstorms are rare events.** In any given place and hour, the answer is
almost always "no storm". A model that always says "no" scores above 95%
accuracy and is completely useless. This single fact shapes the whole
verification approach — see [07-verification.md](07-verification.md).

**The data sources disagree with each other.** Satellite sees cloud tops from
above, radar sees precipitation from below, lightning networks see electrical
activity, and models see a simulated atmosphere. They have different
resolutions, different update rates, and different failure modes. Fusing them
means handling the case where one is missing or stale.

**Convective initiation is genuinely difficult.** Tracking an existing storm
is tractable — it moves roughly with the mid-level wind and optical flow
handles it well. Predicting where a *new* storm will form in currently clear
air is much harder, and it is where most of the remaining forecast value sits.

**Ground truth is not freely available.** Lightning strike archives for India
sit behind institutional access. Without labels there is no supervised
learning, which is the single biggest constraint on this project today.

---

## How we interpreted the scope

| Requirement | Our interpretation | Where it is implemented |
|---|---|---|
| Multiple radars | Fetch the nearest Doppler sites, decode reflectivity, merge with inverse-distance weighting, and report which sites actually contributed | `utils/datasources/radar.py` |
| Satellite | INSAT-3DS and 3DR infrared, water vapour, visible and mid-IR channels, georeferenced and calibrated | `utils/datasources/mosdac.py` |
| Lightning | Strike density, cloud-to-ground ratio and the lightning jump as predictors; strike occurrence in a forward window as the training label | `utils/datasources/lightning.py` |
| Model data | Convective parameters — CAPE, CIN, Lifted Index, deep-layer shear, precipitable water | `utils/datasources/nwp.py` |
| Nowcasting 0–6 h | Optical-flow advection to six lead times, plus a learned probability | `utils/optical_flow.py` |
| AI/ML | Gradient-boosted trees over 88 named features, bound by a feature contract | `utils/predictor.py` |

---

## What we deliberately did not do

**We did not use deep learning.** Not because it is unsuitable — published
work shows convolutional and recurrent architectures do well at nowcasting —
but because they need a large labelled archive that we do not yet have.
Claiming a deep model trained on synthetic data would be worse than useless.

**We did not draw boundaries from international datasets.** Natural Earth,
OpenStreetMap and GADM all depict the Line of Control rather than the official
Indian boundary. All boundaries come from ISRO Bhuvan, which carries the
Survey of India depiction.

**We did not quote an accuracy figure.** See
[07-verification.md](07-verification.md) for why accuracy is the wrong metric
for this problem, and what we report instead.
