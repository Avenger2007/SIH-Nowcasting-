# 06 · The Science

Why each feature and threshold is there. This is the document to read before
defending the approach to a meteorologist.

---

## The ingredients of a thunderstorm

Three things must coincide. The system measures all three.

| Ingredient | What it means | Measured by |
|---|---|---|
| **Moisture** | Water vapour available to condense and release latent heat | Precipitable water, dew point depression, relative humidity |
| **Instability** | The atmosphere lets a lifted parcel keep rising | CAPE, Lifted Index, 850–500 hPa lapse rate |
| **Lift** | Something to start the parcel rising | Low-level convergence, diurnal heating, terrain |

A fourth ingredient, **shear**, does not cause storms but organises them.
Weak shear gives short-lived single cells; strong shear gives long-lived
organised systems that travel further and do more damage.

---

## Infrared satellite: reading cloud tops

Infrared radiometers measure the temperature of whatever they see. For an
opaque cloud, that is the cloud top. Because temperature falls with height in
the troposphere, **a colder top means a taller cloud**.

### Thresholds, all in Kelvin

| Threshold | Value | Interpretation |
|---|---|---|
| `BT_CONVECTIVE_K` | 241 K (−32 °C) | Cumulonimbus anvil present |
| `BT_DEEP_CONVECTIVE_K` | 221 K (−52 °C) | Deep convection; lightning likely |
| `BT_OVERSHOOT_K` | 205 K (−68 °C) | Overshooting top; severe storm signature |

An overshooting top is a parcel so buoyant it punches through the tropopause
into the stratosphere. It is one of the strongest visual indicators of a
severe storm.

Expressing thresholds in Kelvin rather than pixel values is not pedantry: an
8-bit browse image and a calibrated NetCDF product use completely different
number ranges for the same physical temperature.

### Cloud-top cooling rate

The single most useful infrared nowcasting signal. A cloud top that is cooling
is a cloud that is growing vertically.

```
cooling_rate = (BT_previous − BT_now) / minutes_between_scans
```

Sustained cooling above roughly **0.25 K/min** marks vigorous convection,
typically producing lightning within the hour. This measures *development*,
which a single snapshot cannot.

### Texture and cell geometry

Convective tops are lumpy; stratiform cloud is smooth. Local standard
deviation, gradient magnitude and Laplacian capture this.

**Compactness** — `4π·area / perimeter²` — separates a compact vigorous cell
from a sprawling decaying anvil covering the same area. A mature storm has a
tight, near-circular core; a dying one spreads and frays.

### Split-window difference (IR1 − IR2)

Thick convective anvils behave nearly as black bodies in both channels, so the
difference is near zero. Thin cirrus is semi-transparent and shows a large
positive difference. This distinguishes an active storm top from leftover high
cloud debris — something single-channel infrared cannot do.

---

## Radar: seeing inside the storm

Radar measures backscatter from precipitation, reported in dBZ.

| Reflectivity | Interpretation |
|---|---|
| < 20 dBZ | Light drizzle or cloud droplets |
| 20–35 dBZ | Light to moderate rain |
| **35–50 dBZ** | Convective core |
| **> 50 dBZ** | Intense core; hail possible |
| > 60 dBZ | Large hail likely |

Radar complements satellite exactly where satellite is weakest. Infrared sees
only the top; radar sees the precipitation structure beneath it. A cold top
with no radar echo may be old cirrus, while a warm top with a 55 dBZ core is
an active low-topped storm.

Radial velocity (`ppv`) reveals rotation, the mesocyclone signature — captured
in the module but not yet used as a feature.

---

## Lightning: predictor and target

**As a predictor.** Strike density and its rate of change are among the
strongest short-range signals that a cell is electrically active and will
remain so over the next 30 to 90 minutes.

**The lightning jump.** A rapid increase in intracloud flash rate typically
precedes severe weather at the surface by 10 to 20 minutes. The system
computes:

```
jump_ratio = (strike rate, last 15 min) / (strike rate, preceding 45 min)
```

**As a target.** A sample at time *t* is labelled positive when at least one
strike occurs within a radius during *(t, t + lead]*. The window is strictly
forward-looking — including strikes at or before *t* would leak the answer
into the features and inflate every score.

---

## Numerical model data: the environment

Satellite and radar show what *is* happening. Model data shows whether the
atmosphere *supports* more.

### CAPE — the fuel

Convective Available Potential Energy, in J/kg — the integrated buoyancy
available to a rising parcel.

| CAPE | Interpretation |
|---|---|
| < 300 | Negligible instability |
| 300–1000 | Marginal; isolated weak cells |
| 1000–2500 | Moderate; thunderstorms supported |
| > 2500 | Strong; severe convection possible |

### CIN — the lid

Convective Inhibition. Energy that must be supplied *before* a parcel can rise
freely. High CAPE with high CIN is a loaded gun with the safety on: nothing
happens until something breaks the cap — usually afternoon heating or terrain
lift. When it does break, the release can be explosive.

### Lifted Index, K-index, Total Totals

Classical stability indices that IMD forecasters read directly. LI is the
temperature difference between a lifted parcel and its environment at 500 hPa;
negative means unstable.

### Deep-layer shear

The 10 m to 500 hPa vector wind difference.

| Shear | Storm mode |
|---|---|
| < 10 m/s | Single cell, short-lived |
| 10–18 m/s | Multicell clusters |
| > 18 m/s | Organised, long-lived systems |

---

## Cloud motion: Lagrangian persistence

Optical flow measures the apparent motion of cloud features between
consecutive scans. Advecting the current field along that motion gives a
forecast — the assumption that features keep moving as they have been moving.

This is the workhorse of 0–2 hour nowcasting and is **genuinely hard to beat**
at short lead times. It is used here both as a feature source and as the
baseline against which the model must demonstrate skill.

**Convergence beneath cold cloud.** Convergence is negative divergence — air
flowing together, forcing ascent. Measured across the whole scene it is
diluted by clear-air noise. Measured *only beneath cold cloud tops*, it
locates where new cells are developing.

---

## The diurnal cycle

Indian thunderstorms have a strong afternoon maximum, typically 14:00–18:00
IST. Surface heating erodes the capping inversion; once broken, stored CAPE
is released.

Hour of day is encoded both raw and cyclically (`sin`, `cos`), because hour 23
and hour 0 are adjacent and a tree should not have to learn that from scratch.
Monsoon-season and afternoon-peak flags carry the seasonal and diurnal
structure explicitly.

---

## Known scientific limitations

**Uncalibrated brightness temperature.** Public browse imagery is a rendered
8-bit product; Kelvin is inferred from an assumed linear stretch and the scene
saturates at the cold end. Absolute values carry systematic error; relative
structure and cooling rates remain usable.

**Convective initiation is not solved.** Optical flow extrapolates existing
cells well. Predicting *new* cells in currently clear air is far harder, and
is where most remaining forecast value lies.

**Parallax is not corrected.** A tall cloud viewed obliquely from
geostationary orbit appears displaced from its true ground position, by tens
of kilometres at the edges of the Indian domain.

**Single-level analysis.** The system works with cloud-top temperature and
column-integrated parameters. Full vertical profiles from the INSAT sounder
would add genuine information.
