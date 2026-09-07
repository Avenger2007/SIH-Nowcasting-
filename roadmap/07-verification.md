# 07 · Verification

How skill is measured, and why the obvious metric is banned.

---

## Why accuracy is forbidden here

Thunderstorms are rare. In any given place and hour the answer is almost
always "no storm".

Take a realistic base rate of 5%. A model that outputs "no storm" every single
time achieves:

| Metric | Value |
|---|---|
| Accuracy | **95%** |
| Probability of Detection | **0.00** |
| Critical Success Index | **0.00** |
| Lives saved | **zero** |

Ninety-five percent accuracy, and it never once warns anybody. This is not a
hypothetical — it is the single most common way machine-learning results on
rare events are misreported.

The project has a test that asserts exactly this
(`test_accuracy_is_misleading_for_rare_events`), and accuracy is only ever
displayed beside the base rate that makes it interpretable.

---

## The contingency table

Operational meteorology verifies against a 2×2 table. Everything else derives
from it.

|  | Observed yes | Observed no |
|---|---|---|
| **Forecast yes** | hits (a) | false alarms (b) |
| **Forecast no** | misses (c) | correct negatives (d) |

### The metrics we report

| Metric | Formula | Perfect | Reads as |
|---|---|---|---|
| **POD** | a / (a+c) | 1.0 | Of storms that happened, what fraction did we catch? |
| **FAR** | b / (a+b) | 0.0 | Of warnings issued, what fraction were wrong? |
| **CSI** | a / (a+b+c) | 1.0 | Threat score — the headline number |
| **Bias** | (a+b) / (a+c) | 1.0 | Over- or under-forecasting |
| **HSS** | vs random chance | 1.0 | Skill beyond guessing |
| **PSS** | POD − POFD | 1.0 | Ability to discriminate |

**CSI is the number to quote.** It ignores correct negatives entirely, which
is exactly right for a rare event: correctly saying "no storm" on a clear
January night is not an achievement.

**POD and FAR trade off.** Lower the threshold and you catch more storms but
cry wolf more often. This is a policy decision, not a technical one — the cost
of a missed lightning death versus the cost of eroding public trust. The
system exposes the threshold and reports the CSI-optimal value rather than
silently defaulting to 0.5.

---

## Probabilistic metrics

The model outputs a probability, not a yes/no, so it is also scored as one.

**Brier score** — mean squared error of the probability. Lower is better.

**Brier Skill Score** — the honest headline. Brier score relative to always
forecasting climatology:

```
BSS = 1 − BS / BS_climatology
```

BSS = 0 means no better than quoting the long-term average. **Positive means
genuine skill.** A model can have a good-looking Brier score and zero skill.

**Reliability curve** — of the times we said 70%, did it happen 70% of the
time? A confident-but-wrong model shows up here immediately, where aggregate
scores can hide it.

**ROC / AUC** — computed exactly, using the Mann-Whitney rank identity rather
than integrating a sampled curve. Integrating the sampled curve understates
the area, because many thresholds share the same false-alarm rate and the
trapezoid rule then integrates through a vertical segment. Perfectly separable
data scored 0.833 instead of 1.0 that way — logged as `BUG-028`.

---

## The two rules that make results meaningful

### 1 · Temporal splits, never random

A random train/test split puts frames **from the same storm** in both sets.
The model is then scored on weather it has already seen, and skill is inflated
enormously. This is the most common methodological error in nowcasting
papers.

The last portion **in time** is held out. `ThunderstormPredictor.train()`
defaults to `split_strategy="temporal"`.

### 2 · Always report against a baseline

A CSI of 0.45 means nothing on its own. The question is always: **better than
what?**

The baseline here is **persistence** — assume current conditions continue.
For lightning specifically: "there were strikes in the last hour, so there
will be strikes in the next three." Simple, and genuinely hard to beat at
short lead times.

```
CSI_skill = (CSI_model − CSI_baseline) / (1 − CSI_baseline)
```

Positive means the model adds value. Negative means it does not, and that must
be reported honestly rather than buried.

---

## The label definition

Verification is only as meaningful as the event definition. Ours:

> A sample at time *t* is **positive** when at least `min_strikes` lightning
> strikes occur within `radius_km` of the point during the window
> *(t, t + lead_hours]*.

Defaults: 1 strike, 25 km, 3 hours.

**The window is strictly forward-looking.** Including strikes at or before *t*
would leak the answer into the features. `test_lightning_labels_are_forward_looking`
asserts a strike 30 minutes in the past does not create a positive label.

---

## Current results — and what they mean

The shipped model reports, on a held-out temporal split:

| Metric | Value |
|---|---|
| POD | 0.726 |
| FAR | 0.401 |
| CSI | 0.488 |
| HSS | 0.517 |
| ROC AUC | 0.850 |
| Brier Skill Score | 0.321 |

**These numbers measure the verification machinery, not forecast skill.** The
model is fitted to synthetic labels generated from a formula, so it is being
scored on its ability to recover a relationship that was invented. It
demonstrates that the pipeline computes metrics correctly. It says nothing
about the atmosphere.

The dashboard states this above every number, and the model card records
`training_data: synthetic`.

This is stated plainly because the alternative — quoting these as forecast
skill — would not survive the first question from a domain expert, and would
deserve not to.

---

## What real results will look like

Once trained on observed lightning (see
[08-model-roadmap.md](08-model-roadmap.md)), expect:

- **CSI in the 0.25–0.45 range** at 1–3 hour lead. Published operational
  nowcasting systems sit around there. Anything above 0.6 on a rare event
  should be treated as a bug until proven otherwise — usually a leaked label.
- **Skill over persistence that decays with lead time.** Persistence is
  strong at 30 minutes and weak at 6 hours; the model should beat it by more
  as lead time grows.
- **A reliability curve close to the diagonal**, possibly needing isotonic
  calibration.

Reporting a modest CSI that genuinely beats persistence is a far stronger
result than a large number nobody can reproduce.
