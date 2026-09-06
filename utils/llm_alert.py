"""
utils/llm_alert.py
Alert generation - template-based, with optional LLM phrasing.

Fixes from the original:

  * ``generate_detailed_report`` formatted ``features.get('x', 'N/A'):.2f``.
    When a key was missing that evaluates ``format('N/A', '.2f')``, which
    raises ValueError. A missing feature crashed the report instead of
    printing "N/A". Formatting now goes through a helper that checks the type.
  * The Groq model was ``groq/compound``, which is not a chat model id and
    returned HTTP 403. It is now a current Llama model, configurable.
  * ``app.py`` called ``generate_template_alert`` directly, so the LLM was
    unreachable no matter what key was configured. ``generate_alert`` is now
    the single entry point and falls back to templates by itself.

Design note: the LLM only ever REPHRASES numbers the model produced. It is
never asked to judge risk, and a template alert is always generated first as
the fallback - so an LLM outage degrades the wording, never the warning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

import config

# Llama 3.3 70B on Groq. Override with GROQ_MODEL in .env.
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = (
    "You are a duty forecaster at the India Meteorological Department writing "
    "a public nowcast bulletin. Rules: state the risk level and time window "
    "in the first sentence; give concrete safety advice; stay under 60 words; "
    "use plain English a non-specialist can act on; never invent numbers not "
    "given to you; never downplay a HIGH risk."
)


def _fmt(value, spec: str = ".2f", fallback: str = "N/A") -> str:
    """
    Format a value that might be missing.

    This is the fix for the crash: format specs are only applied to numbers.
    """
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return fallback


# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

def generate_template_alert(prediction: Dict,
                            location: str = "Delhi",
                            observation=None) -> str:
    """
    Deterministic alert text. Always available, never fails.

    When the underlying model is a demonstration model, the alert says so in
    its first line - a warning that looks official but is backed by synthetic
    training data is worse than no warning at all.
    """
    risk = prediction.get("risk_level", "MINIMAL")
    probability = prediction.get("thunderstorm_probability", 0.0)

    prefix = ""
    if prediction.get("is_demonstration_only"):
        prefix = "[DEMONSTRATION - not an operational forecast] "

    bodies = {
        "HIGH": (
            f"THUNDERSTORM WARNING for {location}. Model probability "
            f"{probability:.0f}% within the next 0-6 hours. Move indoors and "
            f"stay away from trees, open ground and water. Unplug appliances. "
            f"Farmers and outdoor workers should suspend fieldwork."
        ),
        "MODERATE": (
            f"THUNDERSTORM WATCH for {location}. Model probability "
            f"{probability:.0f}% within the next 0-6 hours. Be ready to move "
            f"indoors at short notice. Secure loose objects and avoid open "
            f"fields during the afternoon peak."
        ),
        "LOW": (
            f"WEATHER ADVISORY for {location}. Isolated thunderstorm activity "
            f"possible, probability {probability:.0f}% over 0-6 hours. Carry "
            f"rain protection and keep an eye on the sky if working outdoors."
        ),
        "MINIMAL": (
            f"No significant thunderstorm activity expected for {location} in "
            f"the next 0-6 hours (probability {probability:.0f}%). Conditions "
            f"likely to remain settled."
        ),
    }

    alert = prefix + bodies.get(risk, bodies["MINIMAL"])

    if observation is not None and getattr(observation, "missing_legs", None):
        missing = observation.missing_legs
        if missing:
            alert += (
                f" [Confidence note: {', '.join(missing)} data unavailable for "
                f"this run.]"
            )

    return alert


# --------------------------------------------------------------------------
# LLM phrasing
# --------------------------------------------------------------------------

def generate_alert(prediction: Dict,
                   location: str = "Delhi",
                   observation=None,
                   api_key: Optional[str] = None,
                   model: Optional[str] = None) -> Dict:
    """
    Single entry point for alert text.

    Returns a dict with the text and how it was produced, so the UI can label
    an LLM-written bulletin as such.
    """
    template = generate_template_alert(prediction, location, observation)

    key = api_key or config.get_secret("GROQ_API_KEY")
    if not config.has_secret("GROQ_API_KEY") and not api_key:
        return {
            "text": template,
            "method": "template",
            "note": "No GROQ_API_KEY configured; using the deterministic "
                    "template. Free keys at console.groq.com.",
        }

    try:
        from groq import Groq

        client = Groq(api_key=key)
        response = client.chat.completions.create(
            model=model or config.get_secret("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_prompt(
                    prediction, location, observation)},
            ],
            max_tokens=200,
            temperature=0.4,
        )
        text = response.choices[0].message.content.strip()

        if prediction.get("is_demonstration_only"):
            text = "[DEMONSTRATION - not an operational forecast] " + text

        return {"text": text, "method": "llm", "note": ""}

    except Exception as exc:
        return {
            "text": template,
            "method": "template",
            "note": f"LLM unavailable ({type(exc).__name__}); "
                    f"using the template. Detail: {str(exc)[:120]}",
        }


def _build_prompt(prediction: Dict, location: str, observation=None) -> str:
    """Assemble the LLM prompt from model output and observed conditions."""
    lines = [
        f"Location: {location}, India",
        f"Risk level: {prediction.get('risk_level')}",
        f"Probability: {prediction.get('thunderstorm_probability', 0):.0f}%",
        "Valid period: next 0-6 hours",
    ]

    if observation is not None:
        features = getattr(observation, "features", {}) or {}
        if features.get("nwp_observed"):
            lines.append(f"CAPE: {_fmt(features.get('cape_j_kg'), '.0f')} J/kg")
            lines.append(f"Lifted Index: {_fmt(features.get('lifted_index'), '+.1f')} K")
        if features.get("radar_observed"):
            lines.append(
                f"Peak radar reflectivity: "
                f"{_fmt(features.get('max_reflectivity_dbz'), '.0f')} dBZ"
            )
        if features.get("lightning_observed"):
            lines.append(
                f"Lightning strikes in the last hour: "
                f"{_fmt(features.get('lightning_strike_count'), '.0f')}"
            )
        note = getattr(observation, "confidence_note", None)
        if callable(note):
            lines.append(f"Data coverage: {note()}")

    lines.append(
        "\nWrite the public bulletin. Do not invent any figure not listed above."
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Technical report
# --------------------------------------------------------------------------

def generate_detailed_report(prediction: Dict,
                             location: str,
                             features: Dict,
                             observation=None,
                             verification: Optional[Dict] = None) -> str:
    """
    Full technical report for the evaluation panel.

    Every numeric field goes through ``_fmt``, so a missing feature renders as
    "N/A" instead of raising ValueError the way the original did.
    """
    now = datetime.now(timezone.utc)

    report = [
        f"# Thunderstorm & Lightning Nowcast - {location}",
        "",
        f"**Issued:** {now:%Y-%m-%d %H:%M} UTC "
        f"({(now.hour + 5) % 24:02d}:{(now.minute + 30) % 60:02d} IST approx.)  ",
        "**Valid:** next 0-6 hours  ",
        f"**Problem statement:** SIH26072, Ministry of Earth Sciences / IMD",
        "",
        "## 1. Nowcast",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Thunderstorm probability | "
        f"{_fmt(prediction.get('thunderstorm_probability'), '.1f')}% |",
        f"| Risk level | {prediction.get('risk_level', 'N/A')} |",
        f"| Binary call | "
        f"{'Thunderstorm expected' if prediction.get('prediction') else 'No thunderstorm'} |",
        "",
    ]

    # Model status - stated before any numbers are interpreted.
    card = prediction.get("model_card", {})
    report += [
        "## 2. Model status",
        "",
        f"> {prediction.get('banner', 'Status unknown.')}",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Training data | {card.get('training_data', 'unknown')} |",
        f"| Training samples | {card.get('n_samples', 'N/A')} |",
        f"| Split strategy | {card.get('split_strategy', 'N/A')} |",
        f"| Trained at | {card.get('trained_at', 'N/A')} |",
        f"| Label definition | {card.get('label_definition', 'N/A')} |",
        "",
    ]

    if prediction.get("out_of_distribution"):
        report += [
            "### Out-of-distribution warnings",
            "",
            "The following inputs sit far outside the range the model was "
            "trained on, so its output for them is extrapolation:",
            "",
        ]
        for item in prediction["out_of_distribution"][:10]:
            low, high = item["training_range"]
            report.append(
                f"- `{item['feature']}` = {_fmt(item['value'], '.2f')} "
                f"(training range {_fmt(low, '.2f')} to {_fmt(high, '.2f')}, "
                f"z = {_fmt(item['z_score'], '.1f')})"
            )
        report.append("")

    # Data provenance.
    if observation is not None:
        report += [
            "## 3. Data provenance",
            "",
            f"{observation.confidence_note()}",
            "",
            "| Leg | Source | Status | Latency | Detail |",
            "|---|---|---|---|---|",
        ]
        for row in observation.provenance():
            report.append(
                f"| {row['leg']} | {row['source']} | **{row['status']}** | "
                f"{row['latency_ms']:.0f} ms | {row['message'][:90]} |"
            )
        report.append("")

    # Key diagnostics.
    report += [
        "## 4. Key diagnostics",
        "",
        "| Parameter | Value | Interpretation |",
        "|---|---|---|",
        f"| Coldest cloud top | {_fmt(features.get('bt_min'), '.1f')} K | "
        f"{_interpret_bt(features.get('bt_min'))} |",
        f"| Deep convective fraction | "
        f"{_fmt(features.get('deep_convective_fraction'), '.1%')} | "
        f"Scene colder than 221 K |",
        f"| Max cooling rate | "
        f"{_fmt(features.get('cooling_rate_max'), '.3f')} K/min | "
        f"{_interpret_cooling(features.get('cooling_rate_max'))} |",
        f"| CAPE | {_fmt(features.get('cape_j_kg'), '.0f')} J/kg | "
        f"{_interpret_cape(features.get('cape_j_kg'))} |",
        f"| CIN | {_fmt(features.get('cin_j_kg'), '.0f')} J/kg | "
        f"Convective inhibition |",
        f"| Lifted Index | {_fmt(features.get('lifted_index'), '+.1f')} K | "
        f"{'Unstable' if (features.get('lifted_index') or 0) < 0 else 'Stable'} |",
        f"| Deep-layer shear | "
        f"{_fmt(features.get('deep_layer_shear_ms'), '.1f')} m/s | "
        f"Storm organisation potential |",
        f"| Peak reflectivity | "
        f"{_fmt(features.get('max_reflectivity_dbz'), '.0f')} dBZ | "
        f"{_interpret_dbz(features.get('max_reflectivity_dbz'))} |",
        f"| Lightning (1 h) | "
        f"{_fmt(features.get('lightning_strike_count'), '.0f')} strikes | "
        f"{'Observed' if features.get('lightning_observed') else 'NOT OBSERVED - no network connected'} |",
        f"| Cloud motion | "
        f"{_fmt(features.get('flow_magnitude_mean'), '.2f')} px/frame | "
        f"Bearing {_fmt(features.get('flow_direction_mean'), '.0f')} deg |",
        "",
    ]

    # Verification.
    if verification and "contingency" in verification:
        from utils import metrics as vmetrics

        report += [
            "## 5. Verification (held-out test set)",
            "",
            vmetrics.format_report(verification),
            "",
        ]
    else:
        report += [
            "## 5. Verification",
            "",
            "No held-out verification metrics are available for this model. "
            "Skill scores (POD, FAR, CSI, Brier) require training against "
            "observed lightning labels - see REAL_DATA_INTEGRATION.md.",
            "",
        ]

    report += [
        "## 6. Method",
        "",
        "1. **Ingestion** - INSAT-3D IR via MOSDAC, IMD DWR composites, "
        "lightning network, NWP convective parameters. Each leg carries "
        "explicit provenance.",
        "2. **Motion** - Farneback dense optical flow on the IR sequence, "
        "advected forward (Lagrangian persistence).",
        "3. **Features** - cloud-top cooling, texture, cell geometry, "
        "convergence, convective indices, radar and lightning statistics.",
        "4. **Model** - gradient-boosted trees, aligned to inputs by a named "
        "feature contract.",
        "5. **Alert** - deterministic template, optionally rephrased by an LLM "
        "that is never allowed to alter the numbers.",
    ]

    return "\n".join(report)


def _interpret_bt(value) -> str:
    if value is None:
        return "N/A"
    try:
        bt = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if bt < config.BT_OVERSHOOT_K:
        return "Overshooting top - severe convection"
    if bt < config.BT_DEEP_CONVECTIVE_K:
        return "Deep convection, lightning likely"
    if bt < config.BT_CONVECTIVE_K:
        return "Convective cloud present"
    return "No deep convection"


def _interpret_cooling(value) -> str:
    if value is None:
        return "N/A"
    try:
        rate = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if rate > config.RAPID_COOLING_K_PER_MIN:
        return "Rapid vertical growth"
    if rate > 0:
        return "Slow growth"
    return "Warming - decaying"


def _interpret_cape(value) -> str:
    if value is None:
        return "N/A"
    try:
        cape = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if cape < 300:
        return "Negligible instability"
    if cape < 1000:
        return "Marginal instability"
    if cape < 2500:
        return "Moderate - storms supported"
    return "Strong - severe possible"


def _interpret_dbz(value) -> str:
    if value is None:
        return "N/A"
    try:
        dbz = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if dbz <= 0:
        return "No radar echo"
    if dbz < 35:
        return "Light precipitation"
    if dbz < 50:
        return "Convective core"
    return "Intense core - hail possible"
