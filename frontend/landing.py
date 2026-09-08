"""
frontend/landing.py
Home page for the nowcasting dashboard.

Structured as a sequence of full-width bands, aerospace-console style: one
statement per band, a hairline rule between them, and a lot of air. An
evaluator opening this cold should understand the problem, the approach, the
live data status and the honest limits by scrolling once.

Everything is drawn from live configuration and the issue register, so the
page cannot drift out of date relative to the running system.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional

import config
from utils import compat

from . import hero as hero_view
from . import immersive
from . import theme

# --------------------------------------------------------------------------
# Problem statement - as published on the SIH portal
# --------------------------------------------------------------------------

PROBLEM_STATEMENT = {
    "id": "SIH26072",
    "title": (
        "AI/ML based nowcasting of thunderstorm and lightning using "
        "atmospheric observation including multiple radars, satellite, "
        "lightning and model data"
    ),
    "organisation": "Ministry of Earth Sciences",
    "department": "India Meteorological Department",
    "category": "Software",
    "theme": "Disaster Management",
}

WHY_IT_MATTERS = [
    ("More deaths than floods or cyclones",
     "Lightning kills more people in India each year than either. The "
     "deaths are concentrated among farmers, herders and outdoor workers - "
     "people who are outside, away from shelter, and often without signal."),
    ("The window is minutes, not days",
     "A cell can grow from first cloud to first strike in under an hour. A "
     "forecast issued for a whole district the previous evening cannot "
     "address that. Nowcasting is a different problem from forecasting."),
    ("The observations already exist",
     "INSAT-3DS scans every thirty minutes. Doppler radars cover the major "
     "population centres. Models publish convective parameters continuously. "
     "The gap is fusing them fast enough to act on."),
]

# Colours are stored as SEMANTIC NAMES, never resolved theme attributes.
#
# Resolving `theme.BLUE` at module level runs during import, so any mismatch
# between this page and the palette raises before Streamlit renders anything -
# the whole app dies over a cosmetic value. That shipped once. Names are
# resolved at render time by `_tint()`, which falls back to a literal, so a
# palette problem now costs one swatch instead of the application.
CAPABILITIES = [
    ("01", "Ingest",
     "Satellite, radar, lightning and model data fetched concurrently. Every "
     "payload records where it came from and how fresh it is.", "blue"),
    ("02", "Locate",
     "The satellite full disk is reprojected from the geostationary view onto "
     "a real latitude and longitude grid, so every pixel has a true "
     "location.", "indigo"),
    ("03", "Track",
     "Dense optical flow measures cloud motion between consecutive scans. "
     "Cells are advected forward to each lead time.", "violet"),
    ("04", "Predict",
     "Eighty-eight named features drive a gradient-boosted model, bound to "
     "its inputs by an explicit feature contract.", "amber"),
    ("05", "Verify",
     "The probability is cross-examined against the physics. When model and "
     "atmosphere disagree, the system says so rather than hiding it.", "green"),
    ("06", "Warn",
     "A plain-language bulletin with the risk level, the valid window and "
     "concrete safety advice.", "red"),
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
     "latitude and longitude grid, and display values are converted to "
     "brightness temperature in Kelvin. Every physical threshold in the "
     "system is expressed in Kelvin, never in pixel values."),
    ("Measure cloud motion",
     "Farneback dense optical flow between consecutive scans yields a motion "
     "field. Cells are advected along it - Lagrangian persistence, the "
     "standard operational method and a hard baseline to beat at short lead "
     "times."),
    ("Engineer features",
     "Cloud-top cooling rate, convective area fractions, texture, cell "
     "geometry, convergence beneath cold cloud, radar reflectivity, lightning "
     "rates and jump ratio, convective indices and diurnal terms."),
    ("Predict under contract",
     "Features are matched to the model by name, never by column position. "
     "The model refuses to load without its feature contract and flags any "
     "input outside the range it was trained on."),
    ("Verify honestly",
     "Skill is reported as POD, FAR, CSI, HSS, Brier score and reliability "
     "against a held-out temporal split and a persistence baseline. Accuracy "
     "appears only beside the base rate that makes it misleading."),
    ("Cross-check and warn",
     "The model's answer is compared against independent physical evidence, "
     "then a bulletin is issued with the risk band, the valid window and "
     "advice for people who are outdoors."),
]

_TINTS = {
    "blue": ("BLUE", "#1273D4"),
    "indigo": ("INDIGO", "#4340C0"),
    "violet": ("VIOLET", "#7550D0"),
    "amber": ("AMBER", "#DC7F06"),
    "green": ("GREEN", "#17834A"),
    "red": ("RED", "#CC2E3C"),
    "slate": ("SLATE", "#61748C"),
}


def _tint(name: str) -> str:
    """Resolve a semantic colour name, falling back to a literal."""
    attribute, fallback = _TINTS.get(name, ("BLUE", "#1273D4"))
    return getattr(theme, attribute, fallback)


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


def immersive_sections(live_legs: List[str], total_legs: int,
                       has_run: bool, counts: Dict[str, int]) -> List[Dict]:
    """
    Panels for the scroll-driven experience.

    Built from the same constants as the classic layout, so the two views can
    never tell different stories about the same system.
    """
    legs_value = f"{len(live_legs)}/{total_legs}" if has_run else f"—/{total_legs}"

    return [
        {
            "eyebrow": f"Smart India Hackathon 2026 &nbsp;—&nbsp; {PROBLEM_STATEMENT['id']}",
            "title": "Nowcasting the storm<br>before it breaks",
            "body": (
                "A 0 to 6 hour thunderstorm and lightning nowcast for India, "
                "fusing INSAT satellite imagery, Doppler weather radar, "
                "lightning detection and numerical model output into a single "
                "calibrated probability."
            ),
            "stats": [
                {"value": "0–6", "label": "Hour horizon"},
                {"value": legs_value, "label": "Live data legs"},
                {"value": "88", "label": "Model features"},
                {"value": str(len(config.DWR_NETWORK)), "label": "Radar sites"},
            ],
        },
        {
            "eyebrow": "The problem",
            "title": "Lightning is India's<br>deadliest weather hazard",
            "body": (
                "It kills more people each year than floods or cyclones, and "
                "the deaths follow a pattern: outdoors, in rural districts, "
                "in the afternoon, among people who cannot reach shelter "
                "quickly."
            ),
            "items": [{"h": t, "b": b} for t, b in WHY_IT_MATTERS[1:]],
        },
        {
            "eyebrow": "The brief",
            "title": "Four sources are named.<br>All four are implemented.",
            "body": (
                "The problem statement asks for multiple radars, satellite, "
                "lightning and model data. A submission that skips any of "
                "them has not answered the question."
            ),
            "items": [
                {"h": "Satellite",
                 "b": "INSAT-3DS and 3DR, live from the MOSDAC public gallery."},
                {"h": "Multiple radars",
                 "b": "IMD Doppler composites, decoded from the printed scale."},
                {"h": "Lightning",
                 "b": "Strike density, cloud-to-ground ratio, the lightning jump."},
                {"h": "Model data",
                 "b": "CAPE, inhibition, Lifted Index, deep-layer shear."},
            ],
        },
        {
            "eyebrow": "Approach",
            "title": "Six stages,<br>from orbit to a bulletin",
            "body": (
                "Satellite imagery is georeferenced through the geostationary "
                "projection, cloud motion measured by dense optical flow, and "
                "88 named features drive a model bound to its inputs by an "
                "explicit contract."
            ),
            "items": [{"h": f"{n} · {t}", "b": b}
                      for n, t, b, _ in CAPABILITIES[:4]],
        },
        {
            "eyebrow": "Verification",
            "title": "We measure skill the way<br>meteorologists do",
            "body": (
                "Thunderstorms are rare, so accuracy is meaningless: always "
                "answering “no storm” scores 95% and saves nobody. We "
                "report POD, FAR and CSI against a temporal split and a "
                "persistence baseline."
            ),
        },
        {
            "eyebrow": "Status",
            "title": "What we claim,<br>and what we do not",
            "body": (
                "The pipeline is real and runs on live government data. The "
                "model is trained on synthetic labels and has no measured "
                "forecast skill yet — every screen says so. Connecting an "
                "observed lightning archive is the one remaining step."
            ),
            "items": [
                {"h": "Working today",
                 "b": "Live INSAT, radar and model data. Real cloud motion. "
                      "A full verification suite and a physical cross-check."},
                {"h": "Not finished",
                 "b": f"Observed training labels. {counts['open']} open issues, "
                      f"each documented with a next step."},
            ],
        },
    ]


def render(st, live_legs: Optional[List[str]] = None,
           total_legs: int = 4, has_run: bool = False,
           immersive_mode: bool = True,
           boundary_uri: Optional[str] = None,
           world_uri: Optional[str] = None,
           radars: Optional[List[Dict]] = None) -> None:
    """
    Draw the landing page.

    Two presentations of the same content:

    * immersive - one full-viewport scroll-driven scene, a pinned globe with
      panels moving over it. This is the version to open in front of an
      audience.
    * classic - the same material as ordinary scrolling sections, which is
      easier to read on a small screen and prints sensibly.

    Both are generated from the same constants, so they cannot disagree.

    Args:
        st: the streamlit module.
        live_legs: data legs currently backed by real observations.
        has_run: whether a nowcast has been produced this session.
        immersive_mode: render the scroll-driven experience.
        boundary_uri: official India boundary texture, as a data URI.
        world_uri: world base map texture, as a data URI.
        radars: radar network rows for the globe.
    """
    live_legs = live_legs or []
    counts = _issue_counts()

    if immersive_mode:
        import streamlit.components.v1 as components

        html, dropped = compat.call_supported(
            immersive.build_immersive_html,
            sections=immersive_sections(live_legs, total_legs,
                                        has_run, counts),
            boundary_uri=boundary_uri,
            world_uri=world_uri,
            radars=radars or [],
            satellites=[
                {"name": s.name, "lon": s.longitude, "status": s.status}
                for s in config.SATELLITES
                if s.altitude_km > 30000 and s.status == "operational"
            ],
            height=780,
        )
        if dropped:
            st.warning(compat.stale_module_warning(
                dropped, "frontend/immersive.py"))

        components.html(html, height=790, scrolling=False)
        return

    # ================= hero =================
    # A live storm, not a picture of one. Generated in a shader, so there is
    # no asset to download and no blank first frame.
    import streamlit.components.v1 as components

    components.html(
        hero_view.build_hero_html(
            headline="Nowcasting the storm<br>before it breaks",
            tagline=(
                "A 0 to 6 hour thunderstorm and lightning nowcast for India, "
                "fusing INSAT satellite imagery, Doppler weather radar, "
                "lightning detection and numerical model output into a single "
                "calibrated probability."
            ),
            eyebrow=f"Smart India Hackathon 2026 — {PROBLEM_STATEMENT['id']}",
            stats=[
                {"value": "0–6", "label": "Hour horizon"},
                {"value": f"{len(live_legs)}/{total_legs}" if has_run
                          else f"—/{total_legs}", "label": "Live data legs"},
                {"value": "88", "label": "Model features"},
                {"value": f"{len(config.DWR_NETWORK)}", "label": "Radar sites"},
            ],
            height=620,
        ),
        height=632,
        scrolling=False,
    )

    if not has_run:
        st.markdown(
            '<div class="banner banner-info">Press '
            '<b>RUN NOWCAST</b> in the sidebar to fetch live INSAT imagery, '
            'Doppler radar and model data for the selected city. '
            'It takes about half a minute.</div>',
            unsafe_allow_html=True,
        )

    # ================= the problem =================
    st.markdown(
        theme.section(
            "Lightning is India's deadliest weather hazard",
            eyebrow_text="The problem",
        ),
        unsafe_allow_html=True,
    )

    problem_cols = st.columns(3)
    for col, (title, body) in zip(problem_cols, WHY_IT_MATTERS):
        col.markdown(
            f'<div class="capability" style="border-top-color:{theme.SKY_300}">'
            f'<div class="capability-h">{title}</div>'
            f'<div class="capability-b">{body}</div></div>',
            unsafe_allow_html=True,
        )

    # ================= problem statement =================
    st.markdown(
        theme.section(
            "Four sources are named. All four are implemented.",
            "The statement asks for multiple radars, satellite, lightning and "
            "model data. A submission that skips any of them has not answered "
            "the question.",
            eyebrow_text="Problem statement",
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        theme.spec_table([
            ("Statement", PROBLEM_STATEMENT["id"]),
            ("Title", PROBLEM_STATEMENT["title"]),
            ("Organisation", PROBLEM_STATEMENT["organisation"]),
            ("Department", PROBLEM_STATEMENT["department"]),
            ("Category", PROBLEM_STATEMENT["category"]),
            ("Theme", PROBLEM_STATEMENT["theme"]),
        ]),
        unsafe_allow_html=True,
    )

    # ================= capabilities =================
    st.markdown(
        theme.section(
            "Six stages, from orbit to a bulletin",
            "Each one is independently inspectable in the tabs above.",
            eyebrow_text="Approach",
        ),
        unsafe_allow_html=True,
    )

    row1 = st.columns(3)
    row2 = st.columns(3)
    for index, (number, title, body, tint_name) in enumerate(CAPABILITIES):
        target = row1[index] if index < 3 else row2[index - 3]
        target.markdown(
            theme.capability(number, title, body, _tint(tint_name)),
            unsafe_allow_html=True,
        )

    # ================= data legs =================
    st.markdown(
        theme.section(
            "Where the numbers come from",
            "Live status of every source named in the problem statement.",
            eyebrow_text="Data",
        ),
        unsafe_allow_html=True,
    )

    legs = [
        ("Satellite",
         "INSAT-3DS and INSAT-3DR infrared, water vapour and visible channels "
         "via the MOSDAC public gallery. No credentials required.",
         "satellite"),
        ("Multiple radars",
         "IMD Doppler Weather Radar composites, decoded to reflectivity from "
         "the colour scale printed inside each product.", "radar"),
        ("Lightning",
         "Strike density, cloud-to-ground ratio and the lightning jump. "
         "Adapters are complete; Indian networks require institutional "
         "access.", "lightning"),
        ("Model data",
         "CAPE, convective inhibition, Lifted Index, deep-layer shear and "
         "precipitable water from numerical model output.", "nwp"),
    ]

    leg_cols = st.columns(4)
    for col, (name, body, key) in zip(leg_cols, legs):
        is_live = key in live_legs
        colour = (_tint("green") if is_live
                  else (_tint("slate") if has_run else _tint("blue")))
        label = ("live" if is_live
                 else ("not connected" if has_run else "run to check"))
        col.markdown(theme.leg_card(name, body, label, colour),
                     unsafe_allow_html=True)

    # ================= pipeline =================
    st.markdown(
        theme.section(
            "What happens when you press run",
            eyebrow_text="Pipeline",
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        "".join(theme.step_row(i + 1, title, body)
                for i, (title, body) in enumerate(PIPELINE_STEPS)),
        unsafe_allow_html=True,
    )

    # ================= honest status =================
    st.markdown(
        theme.section(
            "What we claim, and what we do not",
            "The second half matters more than the first.",
            eyebrow_text="Status",
        ),
        unsafe_allow_html=True,
    )

    verdict_cols = st.columns(2)
    verdict_cols[0].markdown(
        theme.verdict(
            "What works today",
            "Live INSAT imagery, georeferenced to within a few kilometres and "
            "validated against the graticule printed in the source product. "
            "Live radar reflectivity. Live convective parameters. Cloud motion "
            "from real consecutive scans. A complete verification suite, and a "
            "physical cross-check that catches the model disagreeing with the "
            "atmosphere.",
            _tint("green"),
        ),
        unsafe_allow_html=True,
    )
    verdict_cols[1].markdown(
        theme.verdict(
            "What is not finished",
            "The model is trained on synthetic labels, so it has no measured "
            "forecast skill yet. Connecting an observed lightning archive is "
            "the single remaining step, and the training script is written and "
            "waiting. Every screen states this. No number here is presented as "
            "an operational forecast.",
            _tint("amber"),
        ),
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        f'<div class="banner banner-info">'
        f'<b>Engineering register.</b> {counts["total"]} issues tracked, '
        f'{counts["fixed"]} resolved and {counts["open"]} open with a '
        f'documented next step. Every one is readable in the '
        f'<b>Engineering register</b> tab, including the bugs we found in our '
        f'own work. We would rather show the list than claim there is nothing '
        f'on it.</div>',
        unsafe_allow_html=True,
    )

    st.write("")
    st.markdown(
        f'<div style="border-top:1px solid {theme.HAIRLINE};padding-top:20px;'
        f'font-size:.74rem;color:{theme.INK_FAINT};line-height:1.8">'
        f'Satellite imagery: ISRO / MOSDAC &nbsp;&middot;&nbsp; '
        f'Radar products: India Meteorological Department &nbsp;&middot;&nbsp; '
        f'Administrative boundaries: ISRO Bhuvan / National Remote Sensing '
        f'Centre, Survey of India depiction &nbsp;&middot;&nbsp; '
        f'Numerical model data: Open-Meteo, GFS / ECMWF IFS, CC-BY 4.0'
        f'</div>',
        unsafe_allow_html=True,
    )
