"""
app.py
Thunderstorm & Lightning Nowcasting dashboard.

SIH 2026, problem statement 26072
Ministry of Earth Sciences / India Meteorological Department

Single entry point. The original project shipped two near-duplicate dashboards
(app.py and app_enhanced.py) that had already drifted apart, so a fix applied
to one silently missed the other. They are merged here.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
from frontend import globe as globe_view
from frontend import theme
from utils import consistency
from utils import features as feat
from utils import llm_alert, metrics as vmetrics, optical_flow
from utils.calibration import kelvin_to_counts
from utils.datasources import fusion, radar as radar_src
from utils.predictor import FeatureContractError, ThunderstormPredictor

st.set_page_config(
    page_title="Thunderstorm Nowcasting | SIH 2026",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(theme.global_css(), unsafe_allow_html=True)


# ==========================================================================
# Cached resources
# ==========================================================================

@st.cache_resource(show_spinner=False)
def load_predictor():
    """Load the model, training a demonstration model if none exists."""
    predictor = ThunderstormPredictor()
    try:
        predictor.load_model()
        return predictor, None
    except (FileNotFoundError, FeatureContractError) as exc:
        from utils.predictor import train_demo_model
        try:
            return train_demo_model(), str(exc)
        except Exception as inner:
            return None, f"Could not load or train a model: {inner}"


@st.cache_data(ttl=600, show_spinner=False)
def cached_fuse(lat: float, lon: float, name: str, allow_simulation: bool):
    """Fetch all data sources, cached for ten minutes."""
    return fusion.fuse(lat, lon, name, allow_simulation=allow_simulation)


@st.cache_data(ttl=1800, show_spinner=False)
def cached_network_status(limit: int = 12):
    """Probe part of the DWR network for the globe."""
    try:
        return radar_src.network_status(limit=limit)
    except Exception:
        return []


@st.cache_data(show_spinner=False)
def load_issues():
    if not config.ISSUES_PATH.exists():
        return {"issues": []}
    return json.loads(config.ISSUES_PATH.read_text(encoding="utf-8"))


# ==========================================================================
# Pipeline
# ==========================================================================

def run_pipeline(city, allow_simulation: bool):
    """Fetch, fuse, extract features and predict."""
    observation = cached_fuse(city.lat, city.lon, city.name, allow_simulation)

    frames, timestamps = fusion.get_satellite_frames(observation)
    if len(frames) < 2:
        return None, observation, "No satellite frames were returned."

    satellite = observation.sources.get("satellite")
    motion_available = bool(satellite and satellite.data.get("motion_available"))

    flow = optical_flow.compute_optical_flow(frames[-2], frames[-1])
    flow_features = optical_flow.extract_flow_features(flow, frames[-1])

    features = feat.build_features(
        frames[-1], frames[-2], timestamps,
        flow_features=flow_features,
        fused_features=observation.features,
    )

    predictor, _ = load_predictor()
    if predictor is None:
        return None, observation, "No model available."

    prediction = predictor.predict_single(features)
    nowcasts, _ = optical_flow.nowcast_sequence(frames)

    return {
        "features": features,
        "prediction": prediction,
        "frames": frames,
        "timestamps": timestamps,
        "flow": flow,
        "flow_features": flow_features,
        "nowcasts": nowcasts,
        "motion_available": motion_available,
        "predictor": predictor,
    }, observation, None


# ==========================================================================
# Sidebar
# ==========================================================================

with st.sidebar:
    st.markdown("### Configuration")

    city_name = st.selectbox(
        "Forecast location",
        [c.name for c in config.CITIES],
        index=0,
    )
    city = config.get_city(city_name)

    st.caption(f"{city.state} — {city.lat:.4f} N, {city.lon:.4f} E")

    nearest = fusion.nearest_radars(city.lat, city.lon, 3)
    st.markdown("**Nearest radar sites**")
    for entry in nearest:
        mark = "in range" if entry["in_range"] else "out of range"
        st.caption(
            f"{entry['code']} {entry['city']} — "
            f"{entry['distance_km']:.0f} km ({mark})"
        )

    st.divider()

    allow_simulation = st.toggle(
        "Allow simulated fallback",
        value=True,
        help="When off, the satellite leg reports unavailable instead of "
             "substituting a synthetic field. Turn it off to prove that "
             "nothing on screen is fabricated.",
    )

    run = st.button("Run nowcast", type="primary", use_container_width=True)

    if st.button("Clear cache", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    st.markdown("**Credential status**")
    for label, key in [
        ("MOSDAC (calibrated L1B)", "MOSDAC_USERNAME"),
        ("OpenWeatherMap", "OPENWEATHER_API_KEY"),
        ("Groq (LLM alerts)", "GROQ_API_KEY"),
        ("Lightning network", "BLITZORTUNG_USER"),
    ]:
        present = config.has_secret(key)
        st.caption(f"{'configured' if present else 'not set'} — {label}")

    st.caption(
        "Public INSAT imagery, IMD radar and NWP need no credentials and "
        "work as shipped."
    )


# ==========================================================================
# Header
# ==========================================================================

st.markdown(
    theme.hero(
        "Thunderstorm &amp; Lightning Nowcasting",
        "0–6 hour AI/ML nowcast · SIH 26072 · MoES / IMD",
    ),
    unsafe_allow_html=True,
)


# ==========================================================================
# Run
# ==========================================================================

if run or "result" not in st.session_state:
    with st.spinner("Fetching satellite, radar, lightning and model data…"):
        result, observation, error = run_pipeline(city, allow_simulation)
    st.session_state.result = result
    st.session_state.observation = observation
    st.session_state.error = error
    st.session_state.city = city

result = st.session_state.get("result")
observation = st.session_state.get("observation")
error = st.session_state.get("error")
city = st.session_state.get("city", city)

if error:
    st.error(error)

prediction = result["prediction"] if result else None


# --------------------------------------------------------------------------
# Model-status banner: shown before any number is interpreted.
# --------------------------------------------------------------------------

if prediction:
    if prediction["is_demonstration_only"]:
        banner_class = "banner-demo"
    elif prediction["out_of_distribution"]:
        banner_class = "banner-warn"
    else:
        banner_class = "banner-ok"
    st.markdown(
        f'<div class="banner {banner_class}">{prediction["banner"]}</div>',
        unsafe_allow_html=True,
    )

if observation:
    coverage_class = (
        "banner-ok" if observation.coverage_fraction == 1.0
        else "banner-warn"
    )
    st.markdown(
        f'<div class="banner {coverage_class}">'
        f'<b>Data coverage.</b> {observation.confidence_note()}</div>',
        unsafe_allow_html=True,
    )


# ==========================================================================
# Tabs
# ==========================================================================

tab_now, tab_globe, tab_data, tab_model, tab_issues = st.tabs([
    "Nowcast",
    "3D Network",
    "Data sources",
    "Model & verification",
    "Engineering register",
])


# --------------------------------------------------------------------------
# Nowcast
# --------------------------------------------------------------------------

with tab_now:
    if not result:
        st.info("Press **Run nowcast** in the sidebar.")
    else:
        features = result["features"]
        probability = prediction["thunderstorm_probability"]
        band = config.classify_risk(probability)

        cols = st.columns(5)
        cells = [
            ("Thunderstorm probability", f"{probability:.1f}%",
             "next 0–6 hours", band.hex),
            ("Risk level", band.name, "IMD banding", band.hex),
            ("Coldest cloud top", f"{features['bt_min']:.0f} K",
             f"{features['bt_min'] - 273.15:.0f} °C", None),
            ("CAPE", f"{features['cape_j_kg']:.0f}",
             "J/kg — convective fuel", None),
            ("Peak reflectivity", f"{features['max_reflectivity_dbz']:.0f}",
             "dBZ — radar", None),
        ]
        for col, (label, value, sub, color) in zip(cols, cells):
            col.markdown(theme.metric(label, value, sub, color),
                         unsafe_allow_html=True)

        st.write("")
        left, right = st.columns([1.05, 1])

        with left:
            gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=probability,
                number={"suffix": "%", "font": {"size": 46,
                                                "color": theme.TEXT}},
                title={"text": "Thunderstorm probability, 0–6 h",
                       "font": {"size": 13, "color": theme.TEXT_DIM}},
                gauge={
                    "axis": {"range": [0, 100],
                             "tickcolor": theme.TEXT_FAINT,
                             "tickfont": {"color": theme.TEXT_FAINT,
                                          "size": 10}},
                    "bar": {"color": band.hex, "thickness": 0.28},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 0,
                    "steps": [
                        {"range": [0, 20], "color": "rgba(46,204,113,0.16)"},
                        {"range": [20, 40], "color": "rgba(255,197,49,0.16)"},
                        {"range": [40, 70], "color": "rgba(255,140,26,0.18)"},
                        {"range": [70, 100], "color": "rgba(255,59,82,0.20)"},
                    ],
                },
            ))
            gauge.update_layout(
                height=290, margin=dict(t=50, b=10, l=24, r=24),
                paper_bgcolor="rgba(0,0,0,0)",
                font={"color": theme.TEXT},
            )
            st.plotly_chart(gauge, use_container_width=True)

        with right:
            alert = llm_alert.generate_alert(prediction, city.name, observation)
            st.markdown(
                theme.panel(
                    f"Public bulletin — {alert['method']}",
                    f'<div style="font-size:0.95rem;line-height:1.75;'
                    f'color:{theme.TEXT}">{alert["text"]}</div>'
                    + (f'<div style="font-size:0.72rem;margin-top:10px;'
                       f'color:{theme.TEXT_FAINT}">{alert["note"]}</div>'
                       if alert["note"] else ""),
                ),
                unsafe_allow_html=True,
            )

        # Physical consistency --------------------------------------------
        st.markdown("#### Physical consistency check")
        st.caption(
            "The model's probability is cross-checked against independent "
            "physical evidence. When a learned model and the physics "
            "disagree, that is exactly when a forecaster should look."
        )

        report = consistency.check(features, probability, observation)

        level_class = {
            "agree": "banner-ok",
            "minor": "banner-warn",
            "major": "banner-demo",
        }[report.level]
        st.markdown(
            f'<div class="banner {level_class}">{report.summary()}</div>',
            unsafe_allow_html=True,
        )

        verdict_color = {
            "supports": theme.BAD,        # supports convection = higher risk
            "neutral": theme.ACCENT_WARM,
            "opposes": theme.GOOD,
            "unobserved": theme.IDLE,
        }
        ev_rows = "".join(
            f'<div class="src-row" style="border-left-color:'
            f'{verdict_color[e.verdict]}">'
            f'<div class="src-leg">{e.name}</div>'
            f'<div class="src-body">'
            f'<div class="src-name">'
            f'{theme.chip(e.verdict, verdict_color[e.verdict])}</div>'
            f'<div class="src-msg">{e.detail}</div></div>'
            f'<div class="src-lat">weight {e.weight:.1f}</div></div>'
            for e in report.evidence
        )
        st.markdown(
            theme.panel(
                f"Evidence — model {probability:.0f}% vs physical "
                f"{report.physical_probability:.0f}%",
                ev_rows,
            ),
            unsafe_allow_html=True,
        )

        # Imagery ---------------------------------------------------------
        st.markdown("#### Satellite analysis")
        img_cols = st.columns(3)

        with img_cols[0]:
            st.image(
                kelvin_to_counts(result["frames"][-1]),
                caption="INSAT-3D TIR-1 brightness temperature (latest)",
                use_container_width=True,
            )

        with img_cols[1]:
            if result["motion_available"]:
                st.image(
                    optical_flow.visualise_flow(
                        result["flow"], result["frames"][-1]),
                    caption="Cloud motion (Farneback optical flow)",
                    use_container_width=True,
                )
            else:
                st.image(
                    kelvin_to_counts(result["frames"][-1]),
                    caption="Motion unavailable — only one INSAT scan buffered",
                    use_container_width=True,
                )
                st.caption(
                    "MOSDAC publishes only the newest scan, so motion needs a "
                    "second scan. Run scripts/collect_frames.py on a schedule."
                )

        with img_cols[2]:
            st.image(
                kelvin_to_counts(result["nowcasts"][2]),
                caption="Advected nowcast, +3 h (Lagrangian persistence)",
                use_container_width=True,
            )

        # Lead-time series -------------------------------------------------
        st.markdown("#### Convective trend")
        nwp_result = observation.sources.get("nwp")
        if nwp_result and nwp_result.ok and nwp_result.data.get("series"):
            series = nwp_result.data["series"]
            times = series.get("time", [])
            cape = [v if v is not None else 0 for v in series.get("cape", [])]

            trend = go.Figure()
            trend.add_trace(go.Scatter(
                x=times, y=cape, name="CAPE (J/kg)",
                line=dict(color=theme.ACCENT_WARM, width=2.5),
                fill="tozeroy", fillcolor="rgba(255,210,63,0.13)",
            ))
            trend.update_layout(
                height=250, margin=dict(t=26, b=26, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font={"color": theme.TEXT_DIM, "size": 11},
                xaxis=dict(gridcolor="rgba(120,180,255,0.08)"),
                yaxis=dict(gridcolor="rgba(120,180,255,0.08)",
                           title="CAPE (J/kg)"),
                showlegend=False,
            )
            st.plotly_chart(trend, use_container_width=True)

            from utils.datasources.nwp import convective_summary
            summary = convective_summary(nwp_result)
            scols = st.columns(len(summary))
            for col, (key, text) in zip(scols, summary.items()):
                col.markdown(
                    theme.panel(key.replace("_", " "),
                                f'<div style="font-size:0.8rem;'
                                f'color:{theme.TEXT_DIM}">{text}</div>'),
                    unsafe_allow_html=True,
                )


# --------------------------------------------------------------------------
# 3D network
# --------------------------------------------------------------------------

with tab_globe:
    st.markdown("#### Indian observation network")
    st.caption(
        "INSAT geostationary fleet at true sub-satellite longitudes, every IMD "
        "Doppler radar at its published coordinates with range rings scaled to "
        "actual range, and live data flow into the processing hub. "
        "Hover any object for detail."
    )

    with st.spinner("Probing the radar network…"):
        network = cached_network_status(limit=12)

    contributing_codes = set()
    if observation:
        radar_result = observation.sources.get("radar")
        if radar_result and radar_result.ok:
            contributing_codes = {
                s["code"] for s in radar_result.data.get("stations", [])
            }
    for row in network:
        row["contributing"] = row["code"] in contributing_codes

    selected = {
        "name": city.name,
        "lat": city.lat,
        "lon": city.lon,
        "risk": prediction["risk_level"] if prediction else "n/a",
        "probability": (prediction["thunderstorm_probability"]
                        if prediction else 0.0),
    }

    components.html(
        globe_view.build_globe_html(
            selected_city=selected,
            network_status=network,
            source_status={
                leg: r.status.value
                for leg, r in (observation.sources.items() if observation else [])
            },
            height=680,
        ),
        height=690,
        scrolling=False,
    )

    st.markdown("#### Fleet and network inventory")
    inv_left, inv_right = st.columns(2)

    with inv_left:
        rows = "".join(
            f'<div class="src-row" style="border-left-color:'
            f'{theme.GOOD if s.status == "operational" else theme.IDLE}">'
            f'<div class="src-leg">{s.name}</div>'
            f'<div class="src-body">'
            f'<div class="src-name">{s.operator} — {s.longitude:.0f}° E</div>'
            f'<div class="src-msg">{s.note}</div></div></div>'
            for s in config.SATELLITES
        )
        st.markdown(theme.panel("Satellite fleet", rows),
                    unsafe_allow_html=True)

    with inv_right:
        live_count = sum(1 for r in network if r.get("live"))
        rows = "".join(
            f'<div class="src-row" style="border-left-color:'
            f'{theme.ACCENT_WARM if r.get("contributing") else (theme.GOOD if r.get("live") else theme.IDLE)}">'
            f'<div class="src-leg">{r["code"]}</div>'
            f'<div class="src-body">'
            f'<div class="src-name">{r["city"]} — {r["band"]}-band, '
            f'{r["range_km"]} km</div>'
            f'<div class="src-msg">'
            f'{"contributing to this nowcast" if r.get("contributing") else ("publishing" if r.get("live") else "no public feed")}'
            f'</div></div></div>'
            for r in network
        )
        st.markdown(
            theme.panel(
                f"Radar network — {live_count}/{len(network)} probed sites live",
                rows or "<div>Network probe unavailable.</div>",
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            f"{len(config.DWR_NETWORK)} DWR sites are configured; "
            f"{len(network)} were probed for this view to keep it responsive."
        )


# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------

with tab_data:
    if not observation:
        st.info("Run a nowcast to populate the data-source panel.")
    else:
        st.markdown("#### Provenance")
        st.caption(
            "Every payload states where it came from. A simulated field can "
            "never be presented as an observation."
        )

        rows = "".join(
            theme.source_row(
                row["leg"], row["source"], row["status"],
                row["message"], row["latency_ms"],
            )
            for row in observation.provenance()
        )
        st.markdown(theme.panel("Live source status", rows),
                    unsafe_allow_html=True)

        # Feature groups.
        st.markdown("#### Feature values by source")
        if result:
            features = result["features"]
            for group, names in feat.FEATURE_GROUPS.items():
                with st.expander(f"{group} — {len(names)} features"):
                    body = []
                    for name in names:
                        value = features.get(name, 0.0)
                        body.append({
                            "Feature": name,
                            "Value": round(float(value), 4),
                            "Meaning": feat.describe_feature(name),
                        })
                    st.dataframe(body, use_container_width=True,
                                 hide_index=True)


# --------------------------------------------------------------------------
# Model & verification
# --------------------------------------------------------------------------

with tab_model:
    predictor, load_note = load_predictor()

    if predictor is None:
        st.error("No model is available.")
    else:
        card = predictor.card

        st.markdown("#### Model card")
        cols = st.columns(4)
        cols[0].markdown(theme.metric(
            "Training data", card.training_data.upper(),
            "provenance of the labels",
            theme.BAD if card.is_demonstration_only else theme.GOOD,
        ), unsafe_allow_html=True)
        cols[1].markdown(theme.metric(
            "Samples", f"{card.n_samples:,}", "total"), unsafe_allow_html=True)
        cols[2].markdown(theme.metric(
            "Features", str(card.n_features), "contracted"),
            unsafe_allow_html=True)
        cols[3].markdown(theme.metric(
            "Split", card.split_strategy, "evaluation"),
            unsafe_allow_html=True)

        if card.label_definition:
            st.markdown(
                theme.panel("Label definition",
                            f'<div style="font-size:0.82rem;'
                            f'color:{theme.TEXT_DIM}">'
                            f'{card.label_definition}</div>'),
                unsafe_allow_html=True,
            )

        # Verification.
        st.markdown("#### Verification on the held-out test set")
        validation = card.validation or {}

        if "contingency" in validation:
            c = validation["contingency"]

            score_cols = st.columns(5)
            scores = [
                ("POD", c["pod"], "hit rate, perfect 1.0"),
                ("FAR", c["far"], "false alarms, perfect 0.0"),
                ("CSI", c["csi"], "threat score, perfect 1.0"),
                ("HSS", c["hss"], "skill vs chance"),
                ("ROC AUC", validation["auc"], "discrimination"),
            ]
            for col, (label, value, sub) in zip(score_cols, scores):
                col.markdown(theme.metric(label, f"{value:.3f}", sub),
                             unsafe_allow_html=True)

            st.caption(
                f"Base rate {c['base_rate']:.1%} — this is why accuracy "
                f"({c['accuracy']:.1%}) is a misleading metric for a rare "
                f"event, and why POD/FAR/CSI are reported instead."
            )

            v1, v2 = st.columns(2)

            with v1:
                roc = validation.get("roc", {})
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=roc.get("pofd", []), y=roc.get("pod", []),
                    mode="lines", name="Model",
                    line=dict(color=theme.ACCENT, width=2.5),
                ))
                fig.add_trace(go.Scatter(
                    x=[0, 1], y=[0, 1], mode="lines", name="No skill",
                    line=dict(color=theme.IDLE, width=1.5, dash="dash"),
                ))
                fig.update_layout(
                    title="ROC curve", height=330,
                    xaxis_title="Probability of false detection",
                    yaxis_title="Probability of detection",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"color": theme.TEXT_DIM, "size": 11},
                    xaxis=dict(gridcolor="rgba(120,180,255,0.08)"),
                    yaxis=dict(gridcolor="rgba(120,180,255,0.08)"),
                    margin=dict(t=44, b=40, l=50, r=16),
                )
                st.plotly_chart(fig, use_container_width=True)

            with v2:
                rel = validation.get("reliability", {})
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=rel.get("forecast_probability", []),
                    y=rel.get("observed_frequency", []),
                    mode="lines+markers", name="Model",
                    line=dict(color=theme.ACCENT_WARM, width=2.5),
                ))
                fig.add_trace(go.Scatter(
                    x=[0, 1], y=[0, 1], mode="lines", name="Perfect",
                    line=dict(color=theme.IDLE, width=1.5, dash="dash"),
                ))
                fig.update_layout(
                    title="Reliability (calibration)", height=330,
                    xaxis_title="Forecast probability",
                    yaxis_title="Observed frequency",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font={"color": theme.TEXT_DIM, "size": 11},
                    xaxis=dict(gridcolor="rgba(120,180,255,0.08)"),
                    yaxis=dict(gridcolor="rgba(120,180,255,0.08)"),
                    margin=dict(t=44, b=40, l=50, r=16),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown(vmetrics.format_report(validation))

            if card.is_demonstration_only:
                st.warning(
                    "These scores are measured against SYNTHETIC labels. They "
                    "demonstrate that the verification machinery works; they "
                    "say nothing about real forecast skill. Training on "
                    "observed lightning is issue ISSUE-021 in the register."
                )
        else:
            st.info(validation.get("warning", "No verification metrics."))

        # Feature importance.
        st.markdown("#### Feature importance")
        try:
            importance = predictor.feature_importance(top_n=18)
            names = list(importance.keys())[::-1]
            values = list(importance.values())[::-1]

            fig = go.Figure(go.Bar(
                x=values, y=names, orientation="h",
                marker=dict(color=values, colorscale="Blues"),
            ))
            fig.update_layout(
                height=520, paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": theme.TEXT_DIM, "size": 11},
                xaxis=dict(gridcolor="rgba(120,180,255,0.08)",
                           title="Gain"),
                yaxis=dict(gridcolor="rgba(0,0,0,0)"),
                margin=dict(t=16, b=40, l=210, r=16),
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as exc:
            st.info(f"Feature importance unavailable: {exc}")

        # Out-of-distribution.
        if prediction and prediction["out_of_distribution"]:
            st.markdown("#### Out-of-distribution inputs")
            st.caption(
                "These inputs sit far outside the range the model was trained "
                "on, so its output for them is extrapolation. This check is "
                "what makes the original bug impossible to reintroduce "
                "silently."
            )
            st.dataframe(
                [
                    {
                        "Feature": item["feature"],
                        "Value": round(item["value"], 3),
                        "z-score": round(item["z_score"], 1),
                        "Training range": (
                            f"{item['training_range'][0]:.2f} … "
                            f"{item['training_range'][1]:.2f}"
                        ),
                    }
                    for item in prediction["out_of_distribution"]
                ],
                use_container_width=True, hide_index=True,
            )

        # Technical report.
        if result:
            with st.expander("Full technical report"):
                st.markdown(llm_alert.generate_detailed_report(
                    prediction, city.name, result["features"],
                    observation, card.validation,
                ))


# --------------------------------------------------------------------------
# Engineering register
# --------------------------------------------------------------------------

with tab_issues:
    data = load_issues()
    issues = data.get("issues", [])

    fixed = [i for i in issues if i.get("status") == "fixed"]
    open_issues = [i for i in issues if i.get("status") != "fixed"]

    cols = st.columns(4)
    cols[0].markdown(theme.metric(
        "Total tracked", str(len(issues)), "bugs and issues"),
        unsafe_allow_html=True)
    cols[1].markdown(theme.metric(
        "Fixed", str(len(fixed)), "verified in this build", theme.GOOD),
        unsafe_allow_html=True)
    cols[2].markdown(theme.metric(
        "Open", str(len(open_issues)), "documented, with next steps",
        theme.WARN), unsafe_allow_html=True)
    cols[3].markdown(theme.metric(
        "Critical fixed",
        str(len([i for i in fixed if i["severity"] == "critical"])),
        "would have invalidated results", theme.BAD),
        unsafe_allow_html=True)

    st.write("")
    st.caption(
        "This register is the honest engineering record for the project. "
        "Open items are limitations we know about and can describe, which is "
        "a stronger position than claims we cannot defend."
    )

    view = st.radio(
        "Show", ["Open issues", "Fixed", "All"],
        horizontal=True, label_visibility="collapsed",
    )
    severity_filter = st.multiselect(
        "Severity",
        ["critical", "high", "medium", "low"],
        default=["critical", "high", "medium", "low"],
    )

    if view == "Open issues":
        shown = open_issues
    elif view == "Fixed":
        shown = fixed
    else:
        shown = issues

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    shown = sorted(
        [i for i in shown if i.get("severity") in severity_filter],
        key=lambda i: order.get(i.get("severity", "low"), 9),
    )

    if not shown:
        st.info("Nothing matches the current filter.")
    else:
        st.markdown(
            "".join(theme.issue_card(i) for i in shown),
            unsafe_allow_html=True,
        )


# ==========================================================================
# Footer
# ==========================================================================

st.divider()
st.caption(
    f"SIH 2026 · PS 26072 · Ministry of Earth Sciences / IMD — "
    f"generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC. "
    f"Satellite imagery: ISRO/MOSDAC. Radar: IMD. "
    f"NWP: Open-Meteo (GFS/ECMWF, CC-BY 4.0)."
)
