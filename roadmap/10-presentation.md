# 10 · Presentation — slide by slide

Content for the SIH deck. Short lines, one idea per slide. Everything here is
defensible; nothing is inflated.

**Format note:** keep 12–14 slides. Text on slides should be headline-length —
the detail belongs in what you say, not on the wall.

---

## Slide 1 · Title

> **Nowcasting thunderstorms before they strike**
> 0–6 hour thunderstorm and lightning prediction for India
>
> Problem Statement SIH26072
> Ministry of Earth Sciences · India Meteorological Department
>
> Team name · College · 2026

**Say:** one sentence. "We built a working nowcasting pipeline on live
government data, and we will be straight with you about what it can and cannot
do yet."

---

## Slide 2 · The problem

> **Lightning kills more people in India than any other weather hazard**
>
> - More deaths than floods or cyclones
> - Concentrated among farmers, herders, outdoor workers
> - Deaths happen outdoors, in rural districts, in the afternoon

**Visual:** a single stark statistic. No clip art.

**Say:** the victims are people who are outside and cannot get to shelter
quickly. That shapes everything about what a useful warning looks like.

---

## Slide 3 · Why existing warnings fall short

> **The gap is resolution and timing, not effort**
>
> - District-level alerts cover thousands of km² — most see nothing
> - Issued hours ahead; storms form in under an hour
> - Alert fatigue: warn for a whole district often enough and people stop
>   listening

**Say:** this is a nowcasting problem — 0 to 6 hours — which is genuinely
different from forecasting and needs different methods.

---

## Slide 4 · What the problem statement asks

> **Four data sources, named explicitly**
>
> | | |
> |---|---|
> | Multiple radars | plural — a composite |
> | Satellite | INSAT series |
> | Lightning | predictor and target |
> | Model data | numerical weather prediction |
>
> Fused by AI/ML, at 0–6 hour lead

**Say:** we treated all four as mandatory. Read the next slide as our answer
to each.

---

## Slide 5 · What we built — live data

> **All four legs implemented. Three are live with no credentials.**
>
> | Leg | Source | Status |
> |---|---|---|
> | Satellite | INSAT-3DS / 3DR via MOSDAC | **Live** |
> | Radars | IMD Doppler composites | **Live** |
> | Model data | CAPE, CIN, LI, shear | **Live** |
> | Lightning | adapters built | Needs data agreement |

**Visual:** screenshot of the Data sources tab showing real status chips and
latencies.

**Say:** this is not a mock-up. Open it and it fetches from ISRO and IMD right
now.

---

## Slide 6 · The pipeline

> **Ingest → Locate → Track → Predict → Check → Warn**

**Visual:** the six-stage diagram from the home page.

**Say, one line each:**
- **Ingest** — four sources in parallel, each declaring its own provenance
- **Locate** — geostationary projection puts every pixel at a real coordinate
- **Track** — optical flow measures cloud motion; cells advected forward
- **Predict** — 88 features into a gradient-boosted model
- **Check** — the answer is cross-examined against the physics
- **Warn** — plain-language bulletin with a time window and advice

---

## Slide 7 · The science, briefly

> **Three ingredients must coincide**
>
> - **Moisture** — precipitable water, dew point depression
> - **Instability** — CAPE, Lifted Index
> - **Lift** — low-level convergence beneath cold cloud
>
> Plus **shear**, which organises storms and makes them last
>
> Thresholds in Kelvin: 241 K anvil · 221 K deep convection · 205 K
> overshooting top

**Say:** cloud-top cooling rate is the strongest single satellite signal — a
cooling top is a growing storm. Sustained cooling above 0.25 K/min usually
means lightning within the hour.

---

## Slide 8 · Two engineering decisions

> **1 · Features are bound by name, never by position**
> The model refuses to load without its feature contract, and flags any input
> outside its training range.
>
> **2 · Provenance is part of the data type**
> Every payload carries live / cached / stale / simulated / unavailable.
> Simulated data can never be shown as an observation.

**Say:** both exist because we found the opposite in our own earlier code. A
silent column-order mismatch produces confident, meaningless numbers.

---

## Slide 9 · How we measure skill

> **Accuracy is banned in this project**
>
> With a 5% storm rate, always saying "no storm" gives:
>
> | Accuracy | 95% |
> |---|---|
> | Storms caught | **0** |
> | Lives saved | **0** |
>
> We report POD, FAR, **CSI**, HSS, Brier skill — against a **temporal** split
> and a **persistence baseline**

**Say:** this is the metric IMD and WMO actually use. A number without a
baseline means nothing.

---

## Slide 10 · The consistency check

> **When the model and the physics disagree, we say so**
>
> Live example:
> - Model: **87.6% HIGH**
> - Physical evidence: **45.5%**
> - CAPE 250 J/kg, CIN 162 J/kg — capped and stable
>
> The dashboard flags the 42-point gap and shows which evidence points which
> way.

**Say:** we built this after seeing exactly that contradiction on screen. A
system that catches its own inconsistency is safer than one that hides it.

---

## Slide 11 · Honest status

> **What works**
> Live INSAT, radar and model data. Georeferenced to within a few kilometres.
> Real cloud motion. Full verification suite.
>
> **What does not, yet**
> The model is trained on **synthetic labels**. It has no measured forecast
> skill.
>
> **What unblocks it**
> One lightning archive. The training script is already written.

**Say this plainly.** Then: "We would rather show you the label than claim a
number we cannot evidence."

---

## Slide 12 · Engineering register

> **44 issues tracked · 40 resolved · 4 open with next steps**
>
> Including bugs we found in our own work:
> - integer overflow made radar decode terrain as 40 dBZ echo
> - the projection was vertically flipped — the "India" crop was returning
>   southern ocean
> - ROC AUC understated by integrating a sampled curve

**Visual:** the Engineering register tab.

**Say:** every one is visible in the app, open items included. We think that
is a stronger position than a clean slide.

---

## Slide 13 · Roadmap

> **Priority order**
>
> 1. Observed lightning labels — decisive, needs a data agreement
> 2. Multi-season frame archive — automated, already collecting
> 3. Calibrated L1B satellite — free MOSDAC account
> 4. Gridded output — a probability map, not a point
> 5. Full radar network — IMD institutional access

**Say:** items 1, 3 and 5 need permission, not engineering. That is a request
we would make of IMD directly.

---

## Slide 14 · Impact and close

> **Who it serves**
>
> - Farmers and outdoor workers — the people who die
> - District disaster management — targeted, not blanket, alerts
> - IMD forecasters — a screening tool that flags its own uncertainty
>
> **Runs on a laptop. No GPU. No paid API.**

**Close on:** "The pipeline is real. Give us the lightning data and it becomes
a forecast."

---

## Demo slot

Put the live demo **between slides 6 and 7**, or straight after slide 11 if
time is tight. See [11-demo-script.md](11-demo-script.md).

---

## Design guidance

- **Light background.** Rooms are bright and projectors wash out dark slides.
  The dashboard is designed light for the same reason.
- **One idea per slide.** If a slide needs a paragraph, it is two slides.
- **Real screenshots**, never mock-ups. The system works; show it working.
- **No stock imagery** of generic lightning bolts. Use actual INSAT imagery
  from the app — it is more striking and it is yours.
- **Numbers you can defend.** Every figure in this deck is reproducible from
  the repository.

## Words to avoid

| Do not say | Because |
|---|---|
| "99% accurate" | Accuracy is meaningless here, and the claim invites the question that ends the pitch |
| "Real-time AI" | Vague. Say the actual lead time and cadence |
| "Revolutionary" | Evaluators have heard it all day |
| "Village-level resolution" | We do not have it. INSAT is 4 km |
| "Better than IMD" | IMD set the problem. The framing is *assists*, not *replaces* |
