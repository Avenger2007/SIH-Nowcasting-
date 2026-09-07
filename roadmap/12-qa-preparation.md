# 12 · Q&A Preparation

The hard questions, with honest answers. Read this before the evaluation.

The general rule: **never bluff.** Evaluators for a Ministry of Earth Sciences
problem statement include people who do this professionally. A confident wrong
answer is worse than "we have not done that yet, and here is why."

---

## On the model

### "What is your accuracy?"

> We deliberately do not quote accuracy. Thunderstorms occur in roughly 5% of
> samples, so a model that always says "no storm" is 95% accurate and catches
> nothing. We report Probability of Detection, False Alarm Ratio and Critical
> Success Index against a temporal split and a persistence baseline, which is
> what IMD and the WMO use.
>
> And I should be straight with you: our current model is trained on synthetic
> labels, so it has no measured forecast skill yet. The metrics you see verify
> that our verification machinery works.

### "So your model does not work?"

> The pipeline works and runs on live data. The model is a placeholder, and it
> is labelled as one everywhere it appears. What it needs is an observed
> lightning archive — that is the label, and it is behind institutional
> access. The training script is written and waiting.
>
> We could have trained on something and quoted a number. We think showing you
> the honest label is the better engineering position.

### "Why not deep learning?"

> Because deep models need a large labelled archive that we do not have yet.
> Training a ConvLSTM on synthetic labels would be indefensible. Once we have
> one or two seasons of gridded data, a U-Net or ConvLSTM is the natural next
> step, and it is item 10 on our roadmap.
>
> There is also a baseline argument: optical-flow advection is genuinely hard
> to beat at short lead times. Any deep model has to beat that first.

### "How do you handle class imbalance?"

> Class weighting on the positive class, `aucpr` as the evaluation metric
> rather than logloss, and a decision threshold chosen to maximise CSI rather
> than defaulting to 0.5. We also report the base rate alongside every score
> so the imbalance is visible.

---

## On the data

### "Is this real data or a mock-up?"

> Real. Open the Data sources tab and you can see per-source latency for this
> run. Satellite is INSAT-3DS from ISRO's MOSDAC gallery, radar is IMD's
> public Doppler products, model data is a GFS/ECMWF blend.
>
> When a source is unavailable we say so, and if we fall back to a simulator
> it is labelled SIMULATED in the interface. That distinction is enforced in
> the type system, not left to discipline.

### "You said multiple radars — how many are actually working?"

> Three of the thirty-six sites we have mapped publish public products today:
> Delhi, Goa and Jot. So the composite usually has one contributing radar, and
> the interface reports that rather than implying full coverage.
>
> Institutional access to IMD Level-II volume data would fix it, and would
> also give us true dBZ instead of a palette inversion, plus echo top height
> and VIL. That is a request we would make of IMD directly.

### "How do you get reflectivity out of a GIF?"

> The products embed their own colour scale. We locate the legend inside each
> image, read the swatch colours and their dBZ values, and invert that mapping
> — so it adapts if a station uses a different scale. We also detect the
> circular scan area from the terrain basemap so the cross-section panels and
> legend are excluded.
>
> It is an approximation and we say so. Level-II data would remove the need.

### "Where did your boundaries come from?"

> ISRO Bhuvan, operated by the National Remote Sensing Centre under the
> Department of Space. Those layers carry the Survey of India depiction.
>
> We specifically did not use Natural Earth, OpenStreetMap or GADM, because
> they depict the Line of Control rather than the boundary the Government of
> India recognises. If Bhuvan is unreachable we draw no boundary at all — we
> have a test that prevents anyone adding a foreign fallback.

---

## On the science

### "Why 241 Kelvin?"

> It is the standard infrared threshold for cumulonimbus anvil, about −32 °C.
> We also use 221 K for deep convection likely to produce lightning, and 205 K
> for overshooting tops. All thresholds are in Kelvin rather than pixel values,
> because an 8-bit browse image and a calibrated product use completely
> different number ranges for the same temperature.

### "How do you know your satellite imagery is correctly located?"

> We validated it against the graticule burned into the source product. After
> reprojection the 10, 20 and 30 degree parallels land within 0.03 to 0.07
> degrees of their true positions, which is sub-pixel at INSAT's 4 km
> resolution.
>
> That check does not depend on our boundary overlay, which matters — we
> initially validated by eye against the overlay and it fooled us. The
> projection was vertically flipped and we were analysing southern ocean.

### "What about parallax?"

> Not corrected yet, and it is a real limitation. A tall cloud viewed
> obliquely from geostationary orbit appears displaced by tens of kilometres
> near the edges of our domain. We already retrieve cloud-top height and we
> have the viewing geometry, so the correction is a modest addition — it is
> item 9 on the roadmap.

### "Can you predict where new storms form, not just track existing ones?"

> Not well, and that is the honest answer. Optical flow extrapolates existing
> cells effectively. Convective initiation in clear air is the harder problem
> and where most remaining forecast value sits.
>
> The signals we would add are cumulus field detection in the visible and
> mid-IR channels, outflow boundary detection, and terrain forcing. That is
> item 8.

---

## On the engineering

### "What was the hardest bug?"

> An integer overflow in the radar decoder. We computed squared RGB colour
> distances in int16, but a three-channel squared distance reaches 195,000 and
> int16 tops out at 32,767. It wrapped around, so green terrain scored as a
> near colour match and decoded as a 40 dBZ echo. Delhi read 50% rainfall
> coverage on a clear day.
>
> We caught it by cross-checking decoded coverage against the visible image
> rather than trusting the number.

### "Why should we trust the rest of your code?"

> Because we found those bugs and wrote them down. There are thirty-two issues
> in the register, twenty-eight resolved and four open, and each resolved bug
> has a regression test named after it. The open ones have documented next
> steps.
>
> The register is in the app. We would rather show it than claim there is
> nothing on it.

### "Does this need a GPU?"

> No. Optical flow is pure computation and gradient-boosted trees train in
> minutes on CPU. The whole system runs on a laptop, which matters for
> deployment at a state meteorological centre.

---

## On deployment and impact

### "How would IMD actually use this?"

> As a screening tool, not a replacement. It watches continuously and flags
> where and when convective risk is rising, so a duty forecaster's attention
> goes to the right place. The consistency check means it also flags when it
> disagrees with itself, which is a signal worth acting on.
>
> The next step for real operational value is gridded output — a probability
> map rather than a point forecast.

### "How does the warning reach a farmer?"

> That is outside what we built, and I would rather say so than invent an
> answer. The bulletin is generated in plain language with a risk level, a
> time window and specific advice, so it is ready for SMS, cell broadcast or
> an existing app like Damini. Integration with a dissemination channel would
> be a separate piece of work.

### "What does it cost to run?"

> Effectively nothing. Every data source in the live path is free and needs no
> credentials. It runs on a small VM or free-tier hosting. The only paid
> options are the LLM phrasing, which is optional and falls back to templates,
> and commercial lightning data.

---

## Questions to ask them

Evaluators respond well to being asked something real:

- **"Could IMD provide lightning archive access for a project like this?"**
  This is the genuine blocker and they are the department that would know.
- **"Is Level-II radar data available to student projects?"**
- **"What CSI would a system need to reach for IMD to consider it useful?"**
  You will learn what the operational bar actually is.

---

## If you do not know

Say so:

> I do not know. What I can tell you is how we would find out.

That answer costs you far less than a guess that unravels.
