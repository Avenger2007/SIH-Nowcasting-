# 11 · Demo Script

A five-minute live demonstration. Timings assume a warm frame buffer and a
working connection.

---

## Before you start

- [ ] Frame collector has been running at least an hour
- [ ] App already open in a browser tab, home page loaded
- [ ] A second city decided in advance (Kolkata is good — different weather)
- [ ] `scripts/live_test.py` run once as a fallback if the UI misbehaves

---

## Minute 0:00 — Home page

**Show:** the landing page as it opens.

**Say:**
> This is the system. Everything on this page is generated from the running
> configuration, so it cannot drift out of date. The problem statement is
> here, the four data legs the statement asks for are here, and their live
> status is here.

**Point at:** the four data-leg cards.

---

## Minute 0:45 — Run it

**Do:** press **Run nowcast** in the sidebar.

**Say while it runs:**
> It is fetching four sources concurrently right now — INSAT-3DS imagery from
> ISRO's MOSDAC gallery, Doppler radar from IMD, and convective parameters
> from numerical model output. It takes about half a minute, and the satellite
> fetch dominates because it is a two-megapixel full-disk image.

---

## Minute 1:15 — The result

**Show:** the Nowcast tab.

**Say:**
> Probability, risk band, and the bulletin. Note the two banners at the top.
> The first says the model is a demonstration fitted to synthetic data. The
> second says how many data legs were live for this run.
>
> We put those at the top deliberately. It would be easy to hide them.

**Point at:** the demonstration banner. Do not skip past it.

---

## Minute 2:00 — The consistency check

**Show:** scroll to the physical consistency panel.

**Say:**
> This is the part we are most pleased with. The model gives a number. We then
> cross-examine it against the physics independently — CAPE, convective
> inhibition, Lifted Index, radar reflectivity, cloud-top temperature,
> lightning, time of day.
>
> If the model and the atmosphere disagree, the system says so and shows which
> evidence points which way.

**If there is a disagreement on screen, use it.** That is the demo, not a
problem:
> Right now the model says one thing and the physics says another. In an
> operational setting that is exactly when a duty forecaster should look.

---

## Minute 2:45 — Satellite imagery

**Show:** the satellite panel with boundaries switched on.

**Say:**
> This is live INSAT infrared. The state boundaries over it come from ISRO
> Bhuvan, which carries the Survey of India depiction — we did not use Natural
> Earth or OpenStreetMap because those show a different boundary.
>
> The alignment is the point. We reproject the full disk through the
> geostationary projection, and we validated it against the graticule printed
> in the source image — the parallels land within a few hundredths of a
> degree.

---

## Minute 3:15 — The 3D network

**Show:** the 3D Network tab. Rotate the globe once, slowly.

**Say:**
> The INSAT fleet at their true sub-satellite longitudes, and every Doppler
> radar at its published coordinates with range rings scaled to actual range.
> Green means the site is publishing; amber means it contributed to this
> nowcast.
>
> Only three of the thirty-six sites publish public products today. We show
> that rather than implying full coverage.

**Hover one radar** to show the tooltip.

---

## Minute 4:00 — Verification

**Show:** Model & verification tab.

**Say:**
> POD, false alarm ratio, CSI, Heidke skill score, ROC and reliability. This
> is what IMD and the WMO use, because accuracy is meaningless for a rare
> event — always saying "no storm" scores 95% and saves nobody.
>
> These particular numbers measure our verification machinery, not forecast
> skill, because the model is on synthetic labels. We say that here too.

---

## Minute 4:30 — Engineering register

**Show:** Engineering register tab, filtered to open issues.

**Say:**
> Forty-four tracked issues. Forty resolved, four open, each with a
> next step. This includes bugs we found in our own work — an integer overflow
> that made radar read terrain as rainfall, and a projection sign error that
> had us analysing the southern Indian Ocean and calling it India.
>
> We would rather show you the list.

---

## Minute 5:00 — Close

**Say:**
> The pipeline is real and runs on live government data. The one thing it
> needs to become a forecast rather than a demonstration is an observed
> lightning archive — and the training script for that is already written.
>
> That is a data agreement, not more engineering.

---

## If something breaks

**No internet:** the satellite leg falls back to the labelled simulator.
> Notice it now says SIMULATED. That is the system refusing to present
> synthetic data as an observation. Every other panel still works.

**A data leg is down:** entirely normal.
> Government endpoints have outages. The nowcast degrades and states its
> reduced confidence rather than failing.

**Cloud motion unavailable:** the buffer is cold.
> MOSDAC publishes only the newest scan, so motion needs two. The collector
> normally runs on a schedule.

**The app is slow to wake:** it is a free host sleeping. Talk over it — this
is why you open the tab beforehand.

---

## Questions to invite

If asked "what would you do with more time", the answer is
[08-model-roadmap.md](08-model-roadmap.md), in priority order, starting with
lightning labels. Have that answer ready — it shows you know what the hard
part is.
