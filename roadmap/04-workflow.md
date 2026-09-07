# 04 · Workflow — what actually happens

A trace of one nowcast, from pressing the button to the bulletin appearing.
Timings are from a real run for Delhi.

---

## Overview

```
  Run nowcast
       │
       ├──► fetch 4 sources concurrently ─────────────── ~22 s (satellite bound)
       │
       ├──► georeference + calibrate the satellite frame
       │
       ├──► optical flow between the last two scans
       │
       ├──► build 88 named features
       │
       ├──► align to the contract, predict
       │
       ├──► cross-check against physics
       │
       └──► issue the bulletin
```

---

## Step 1 · Concurrent ingestion

`utils/datasources/fusion.py :: fuse()`

Four sources are fetched in parallel — they are independent network calls, and
a slow radar site must not delay the model data.

```
LIVE  nwp        1 395 ms   Open-Meteo / GFS
LIVE  satellite 22 236 ms   INSAT-3DS TIR-1 (10.8 um)
LIVE  radar      4 630 ms   IMD DWR composite (1 radar)
  –   lightning  2 912 ms   no network connected
LIVE  surface        1 ms   derived from the model analysis
```

Each returns a `SourceResult` carrying its status. A failure is not an
exception — it is a status, and the pipeline continues.

The result reports coverage honestly:

> 3/4 data legs are live (satellite, radar, nwp). Missing: lightning.
> Features for the missing legs are zero-filled and the nowcast is
> correspondingly weaker.

**Satellite detail.** The MOSDAC gallery serves only the newest scan, so the
fetch also writes the frame into a rolling buffer keyed by content hash.
Motion becomes available once two *distinct* scans are held. Hashing matters:
without it, re-fetching the same scan would produce a zero motion field and a
nowcast claiming the storm is stationary.

**Radar detail.** The nearest Doppler sites are queried in distance order.
Each product image is decoded to reflectivity using the colour scale **printed
inside that image**, not a hardcoded palette. The PPI disc is located from the
terrain basemap so the cross-section panels and legend are excluded. Surviving
sites are merged with inverse-distance weighting, and the system reports which
sites actually contributed.

---

## Step 2 · Georeference and calibrate

`utils/geo.py`, `utils/calibration.py`

The INSAT full disk arrives as a 2002 × 2242 rendered image covering an entire
hemisphere. Two transformations make it usable:

**Georeferencing.** The Earth disk is located — largest connected component,
then a least-squares circle fit to the limb — and the geostationary projection
resamples the disk onto a regular latitude/longitude grid over India
(66–98° E, 6–38° N).

```
Earth disk centred at (1002, 1242) px, radius 966 px,
sub-satellite point 0 N 82 E. Scale 6364 px/rad.
```

**Calibration.** Display values become brightness temperature in Kelvin. The
burned-in coastline and graticule are inpainted first — they are drawn in
white, which maps to the cold end of the scale, so a graticule line would
otherwise decode as a line of overshooting cloud tops.

Saturation is tracked. Where the scene clips, the reported minimum is a floor
and the UI says so rather than quoting an implausible −93 °C cloud top.

---

## Step 3 · Cloud motion

`utils/optical_flow.py`

Farneback dense optical flow runs between the last two scans on a
contrast-normalised field, so a cold-topped storm does not dominate the
estimate purely through brightness.

```
Mean motion 0.42 px/frame, bearing 309°
```

The latest frame is then advected forward to each lead time. Lead times are
given in hours and converted with the true 30-minute frame interval — six
hours is twelve steps, not six.

Convergence is computed from the flow divergence and, critically, is also
measured **only beneath cold cloud**, where new cells actually develop.
Averaged over the whole scene it is diluted by clear-air noise.

---

## Step 4 · Feature engineering

`utils/features.py`

Eighty-eight features in five groups:

| Group | Count | Examples |
|---|---|---|
| Satellite | 32 | coldest top, deep convective fraction, cooling rate, texture, cell compactness |
| Cloud motion | 10 | speed, bearing (circular mean), convergence beneath cold cloud |
| Temporal | 9 | hour (raw and cyclic), monsoon flag, afternoon peak flag |
| NWP | 9 | CAPE, CIN, Lifted Index, K-index, Total Totals, deep-layer shear |
| Radar | 8 | peak reflectivity, convective fraction, intense-core fraction |
| Lightning | 10 | strike count, IC/CG ratio, lightning jump ratio |
| Surface | 9 | temperature, dew point depression, pressure |

Each group also contributes an `*_observed` indicator, so an unmeasured
channel is distinguishable from a measured zero.

Sample output:

```
Coldest cloud top    : ≤ 180 K (display saturated over 0.3% of the scene)
Deep convective frac : 10.84%
CAPE                 : 1050 J/kg
Lifted Index         : −0.9 K
Peak reflectivity    : 40 dBZ
Lightning observed   : False
```

---

## Step 5 · Prediction

`utils/predictor.py`

The feature mapping is aligned to the model's contract **by name**. Missing
features raise; extra features warn and are ignored; ordering is irrelevant.

The contract also checks the training distribution:

```
Probability: 65.4%  (MODERATE)
DEMONSTRATION MODE — fitted to synthetic data; carries no skill.
12 feature(s) outside the training distribution:
   bt_std                 34.12  (z = 10.5)
   cloud_top_height_max   18.46  (z = 18.3)
```

Those warnings are the system working as intended. They are precisely the
signal that a model trained on the wrong distribution is being asked to
extrapolate.

---

## Step 6 · Physical consistency check

`utils/consistency.py`

The model's probability is compared against independent evidence — CAPE, CIN,
Lifted Index, cloud-top temperature, radar reflectivity, lightning rate and
diurnal timing. Each line of evidence votes supports / neutral / opposes, with
a weight; unobserved channels vote nothing.

A real result:

```
model probability : 87.6%
physical evidence : 45.5%
level             : major disagreement

opposes    w1.4  Instability (CAPE)     250 J/kg — too little energy
opposes    w1.0  Inhibition (CIN)       162 J/kg — strong cap
neutral    w1.1  Lifted Index           −1.0 K — weakly unstable
supports   w1.2  Satellite cloud tops   10.5% colder than 221 K
neutral    w1.3  Radar reflectivity     peak 40 dBZ
unobserved w1.5  Lightning network      no network connected
supports   w0.6  Diurnal timing         within the afternoon maximum
```

The dashboard states the gap plainly. In an operational setting, a
disagreement between the model and the physics is exactly when a human
forecaster should look.

---

## Step 7 · Bulletin

`utils/llm_alert.py`

A deterministic template alert is generated first and always succeeds. If a
language-model key is configured, it may **rephrase** the same numbers — it is
never allowed to change them or to judge risk. An outage degrades the wording,
never the warning.

```
[DEMONSTRATION — not an operational forecast] THUNDERSTORM WATCH for Delhi.
Model probability 65% within the next 0–6 hours. Be ready to move indoors at
short notice. Secure loose objects and avoid open fields during the afternoon
peak. [Confidence note: lightning data unavailable for this run.]
```

Note the three honesty markers: the demonstration prefix, the explicit time
window, and the data-coverage caveat.

---

## What the user sees

| Tab | Contents |
|---|---|
| **Home** | Problem statement, why it matters, the six-stage approach, live data-leg status |
| **Nowcast** | Probability gauge, risk band, bulletin, consistency check, satellite imagery with official boundaries, CAPE trend |
| **3D Network** | Interactive globe: INSAT fleet, Doppler network with range rings, live data flow |
| **Data sources** | Per-leg provenance with status and latency; all 88 feature values grouped by source |
| **Model & verification** | Model card, POD/FAR/CSI/HSS, ROC and reliability curves, feature importance, out-of-distribution table |
| **Engineering register** | All 32 tracked issues, filterable, with resolutions and next steps |
