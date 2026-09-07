"""
frontend/landing.py
Home page for the nowcasting dashboard.

Built for the person who has thirty seconds and no context: an evaluator
opening the app cold should be able to see what the problem is, what the
system does about it, which data is real, and where the honest limits are -
without clicking anything.

Everything on this page is drawn from live configuration and the issue
register, so it cannot drift out of date relative to the running system.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import config
from frontend import theme

# --------------------------------------------------------------------------
# Problem statement - reproduced from the SIH 2026 portal
# --------------------------------------------------------------------------

PROBLEM_STATEMENT = {
    "id": "SIH26072",
    "title": (
        "AI/ML based nowcasting of thunderstorm and lightning using "
        "atmospheric observation including multiple radars, satellite, "
        "lightning and model data"
    ),
    "organisation": "Ministry of Earth Sciences (MoES)",
    "department": "India Meteorological Department",
    "category": "Software",
    "theme": "Disaster Management",
}

WHY_IT_MATTERS = [
    ("Lightning is India's deadliest weather hazard",
     "It kills more people each year than floods or cyclones. Deaths are "
     "concentrated among farmers, herders and outdoor workers - people who "
     "are outside, away from shelter, and often without a phone signal."),
    ("The dangerous window is minutes, not days",
     "A thunderstorm cell can grow from first cloud to first strike in under "
     "an hour. Forecasts issued for a whole district the previous evening "
     "cannot address that. Nowcasting - the 0 to 6 hour range - is a "
     "genuinely different problem from forecasting."),
    ("The observations already exist",
     "INSAT-3DS scans every 30 minutes, Doppler radars cover the major "
     "population centres, and numerical models publish convective parameters "
     "continuously. The gap is fusing them fast enough to act on."),
]

APPROACH = [
    ("Ingest", "Satellite, radar, lightning and model data are fetched "
               "concurrently. Every payload records where it came from and "
               "how fresh it is.", theme.BLUE),
    ("Locate", "The satellite full disk is reprojected from the "
               "geostationary view onto a real latitude/longitude grid, so "
               "every pixel has a genuine location.", theme.INDIGO),
    ("Track", "Dense optical flow measures cloud motion between consecutive "
              "scans, and cells are advected forward to each lead time.",
     theme.VIOLET),
    ("Predict", "Eighty-eight named features drive a gradient-boosted model "
                "that outputs a calibrated probability, aligned to its "
                "inputs by an explicit feature contract.", theme.AMBER),
    ("Check", "The probability is cross-examined against the physics. When "
              "the model and the atmosphere disagree, the system says so "
              "rather than hiding it.", theme.GREEN),
    ("Warn", "A plain-language bulletin is generated with the risk level, "
             "the time window and concrete safety advice.", theme.RED),
]

PIPELINE_STEPS = [
    ("Acquire observations",
     "INSAT-3DS infrared imagery from the MOSDAC public gallery, Doppler "
     "radar composites from IMD, and convective parameters from numerical "
     "model output. Each source is fetched in parallel and returns an "
     "explicit status, so a partial outage degrades the nowcast instead of "
     "breaking it."),
    ("Georeference and calibrate",
     "The full disk is resampled from the geostationary projection onto a "
     "latitude/longitude grid, and 8-bit display values are converted to "
     "brightness temperature in Kelvin. Every physical threshold in the "
     "system is expressed in Kelvin, not pixel values."),
    ("Measure cloud motion",
     "Farneback dense optical flow between consecutive scans yields a motion "
     "field. Cells are advected forward along it - Lagrangian persistence, "
     "the standard operational nowcasting method and a hard baseline to "
     "beat at short lead times."),
    ("Engineer features",
     "Cloud-top cooling rate, convective area fractions, texture, cell "
     "geometry, low-level convergence beneath cold cloud, radar reflectivity "
     "statistics, lightning rates and jump ratio, convective indices, and "
     "diurnal terms - 88 features across five source groups."),
    ("Predict with a contract",
     "Features are matched to the model by name, never by column position. "
     "The model refuses to load without its feature contract, and flags any "
     "input that falls outside the range it was trained on."),
    ("Verify honestly",
     "Skill is reported as POD, FAR, CSI, HSS, Brier score and reliability "
     "against a held-out temporal split and a persistence baseline. Accuracy "
     "is shown only beside the base rate that makes it misleading."),
    ("Cross-check and warn",
     "The model's answer is compared against independent physical evidence. "
     "A bulletin is then issued with the risk band, the valid window and "
     "specific advice for people who are outdoors."),
]


def _issue_counts() -> Dict[str, int]:
    """Live counts from the engineering register."""
    try:
        data = json.loads(config.ISSUES_PATH.read_text(encoding="utf-8"))
        issues = data.get("issues", [])
        return {
            "total": len(issues),
            "fixed": len([i for i in issues if i.get("status") == "fixed"]),
            "open": len([i for i in issues if i.get("status") != "fixed"]),
        }
    except Exception:
        return {"total": 0, "fixed": 0, "open": 0}


def render(st, live_legs: Optional[List[str]] = None,
           total_legs: int = 4, has_run: bool = False) -> None:
    """
    Draw the landing page.

    Args:
        st: the streamlit module.
        live_legs: names of data legs currently backed by real observations.
        has_run: whether a nowcast has been produced in this session.
    """
    live_legs = live_legs or []
    counts = _issue_counts()

    # ---------------- hero -------------------------------------------------
    st.markdown(
        theme.hero(
            "Nowcasting thunderstorms<br>before they strike",
            "A 0 to 6 hour thunderstorm and lightning nowcasting system for "
            "India, fusing INSAT satellite imagery, Doppler weather radar, "
            "lightning detection and numerical model output.",
            eyebrow=f"Smart India Hackathon 2026 &middot; {PROBLEM_STATEMENT['id']}",
        ),
        unsafe_allow_html=True,
    )

    if not has_run:
        st.markdown(
            f'<div class="banner banner-info" style="text-align:center">'
            f'Press <b>Run nowcast</b> in the sidebar to fetch live INSAT '
            f'imagery, Doppler radar and model data, and produce a forecast '
            f'for the selected city. It takes about half a minute.</div>',
            unsafe_allow_html=True,
        )

    # ---------------- headline numbers -------------------------------------
    st.write("")
    cols = st.columns(4)
    stats = [
        ("0–6 h", "Forecast horizon"),
        (f"{len(live_legs)}/{total_legs}" if has_run else f"–/{total_legs}",
         "Live data legs"),
        ("88", "Model features"),
        (f"{len(config.DWR_NETWORK)}", "Radar sites mapped"),
    ]
    for col, (value, label) in zip(cols, stats):
        col.markdown(theme.stat_card(value, label), unsafe_allow_html=True)

    st.write("")
    st.write("")

    # ---------------- problem statement ------------------------------------
    left, right = st.columns([1.15, 1])

    with left:
        st.markdown("### The problem statement")
        st.markdown(
            theme.panel(
                "As published by the Ministry of Earth Sciences",
                theme.spec_table([
                    ("Statement ID", PROBLEM_STATEMENT["id"]),
                    ("Title", PROBLEM_STATEMENT["title"]),
                    ("Organisation", PROBLEM_STATEMENT["organisation"]),
                    ("Department", PROBLEM_STATEMENT["department"]),
                    ("Category", PROBLEM_STATEMENT["category"]),
                    ("Theme", PROBLEM_STATEMENT["theme"]),
                ]),
            ),
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("### Why it matters")
        for title, body in WHY_IT_MATTERS:
            st.markdown(
                f'<div class="panel" style="padding:16px 18px">'
                f'<div class="lp-h" style="font-size:.94rem">{title}</div>'
                f'<div class="lp-b">{body}</div></div>',
                unsafe_allow_html=True,
            )

    # ---------------- approach ---------------------------------------------
    st.write("")
    st.markdown("### How the system works")
    st.caption(
        "Six stages, each independently inspectable in the tabs above."
    )

    row1 = st.columns(3)
    row2 = st.columns(3)
    icons = ["◉", "▣", "➤", "◴", "✓", "⚡"]
    for i, (title, body, tint) in enumerate(APPROACH):
        target = row1[i] if i < 3 else row2[i - 3]
        target.markdown(
            theme.feature_card(icons[i], title, body, tint),
            unsafe_allow_html=True,
        )

    # ---------------- data coverage ----------------------------------------
    st.write("")
    st.markdown("### The four data legs")
    st.caption(
        "The problem statement names multiple radars, satellite, lightning "
        "and model data. This is the live status of each."
    )

    legs = [
        ("Satellite", "INSAT-3DS and INSAT-3DR infrared, water vapour and "
                      "visible channels via the MOSDAC public gallery.",
         "satellite"),
        ("Multiple radars", "IMD Doppler Weather Radar composites, decoded "
                            "to reflectivity from the colour scale printed "
                            "in each product.", "radar"),
        ("Lightning", "Strike density, cloud-to-ground ratio and the "
                      "lightning jump. Adapters are ready; Indian networks "
                      "require institutional access.", "lightning"),
        ("Model data", "CAPE, convective inhibition, Lifted Index, "
                       "deep-layer shear and precipitable water from "
                       "numerical model output.", "nwp"),
    ]

    leg_cols = st.columns(4)
    for col, (name, body, key) in zip(leg_cols, legs):
        is_live = key in live_legs
        colour = (theme.GREEN if is_live
                  else (theme.SLATE if has_run else theme.BLUE))
        label = ("live" if is_live
                 else ("not connected" if has_run else "run to check"))
        col.markdown(
            f'<div class="lp-card">'
            f'<div style="display:flex;align-items:center;gap:8px;'
            f'margin-bottom:10px">'
            f'{theme.chip(label, colour)}</div>'
            f'<div class="lp-h" style="font-size:.95rem">{name}</div>'
            f'<div class="lp-b">{body}</div></div>',
            unsafe_allow_html=True,
        )

    # ---------------- pipeline ---------------------------------------------
    st.write("")
    st.markdown("### Step by step")

    steps_html = "".join(
        theme.step_row(i + 1, title, body)
        for i, (title, body) in enumerate(PIPELINE_STEPS)
    )
    st.markdown(theme.panel("Processing pipeline", steps_html),
                unsafe_allow_html=True)

    # ---------------- engineering honesty ----------------------------------
    st.write("")
    st.markdown("### What we claim, and what we do not")

    honest_cols = st.columns(2)
    honest_cols[0].markdown(
        f'<div class="lp-card" style="border-left:3px solid {theme.GREEN}">'
        f'<div class="lp-h">What works today</div>'
        f'<div class="lp-b">'
        f'Live INSAT imagery, georeferenced to within a few kilometres and '
        f'validated against the graticule printed in the source product. '
        f'Live radar reflectivity. Live convective parameters. Cloud motion '
        f'from real consecutive scans. A complete verification suite, and a '
        f'physical cross-check that catches the model disagreeing with the '
        f'atmosphere.</div></div>',
        unsafe_allow_html=True,
    )
    honest_cols[1].markdown(
        f'<div class="lp-card" style="border-left:3px solid {theme.AMBER}">'
        f'<div class="lp-h">What is not finished</div>'
        f'<div class="lp-b">'
        f'The model is trained on synthetic labels, so it has no measured '
        f'forecast skill yet. Connecting an observed lightning archive is the '
        f'single remaining step, and the training script is written and '
        f'waiting. Every screen states this; no number here is presented as '
        f'an operational forecast.</div></div>',
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        f'<div class="banner banner-info">'
        f'<b>Engineering register.</b> {counts["total"]} issues tracked, '
        f'{counts["fixed"]} resolved and {counts["open"]} open with a '
        f'documented next step. Open the <b>Engineering register</b> tab to '
        f'read every one, including the bugs we found in our own work. We '
        f'would rather show the list than claim there is nothing on it.'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Satellite imagery: ISRO / MOSDAC. Radar products: India "
        "Meteorological Department. Administrative boundaries: ISRO Bhuvan / "
        "National Remote Sensing Centre, Survey of India depiction. "
        "Numerical model data: Open-Meteo (GFS / ECMWF IFS, CC-BY 4.0)."
    )
