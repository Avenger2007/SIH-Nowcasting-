"""
utils/consistency.py
Cross-check the model's probability against independent physical evidence.

Motivation, from a real run during development: the dashboard reported an 87.6%
HIGH risk for Delhi while the NWP panel directly beneath it said "negligible
instability, strong capping inversion" at 250 J/kg CAPE. Both numbers were
computed correctly. They simply disagreed, because the model is fitted to
synthetic labels and does not know what CAPE means.

A judge would spot that contradiction instantly, and "our system contradicted
itself and did not notice" is far worse than "our system flagged the
contradiction". So the disagreement is now detected, scored and displayed.

This is also genuinely useful in an operational system: when a learned model
and the physics disagree, that is exactly when a human forecaster should look.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import config


@dataclass
class Evidence:
    """One independent line of physical evidence for or against convection."""

    name: str
    verdict: str            # supports | neutral | opposes | unobserved
    detail: str
    weight: float = 1.0

    @property
    def score(self) -> float:
        """+1 supports deep convection, -1 opposes, 0 neutral/unobserved."""
        return {"supports": 1.0, "opposes": -1.0}.get(self.verdict, 0.0)


@dataclass
class ConsistencyReport:
    model_probability: float
    evidence: List[Evidence] = field(default_factory=list)

    @property
    def observed(self) -> List[Evidence]:
        return [e for e in self.evidence if e.verdict != "unobserved"]

    @property
    def physical_score(self) -> float:
        """
        Weighted evidence score in [-1, 1].

        Positive means the observations and model fields support convection.
        """
        observed = self.observed
        if not observed:
            return 0.0
        total_weight = sum(e.weight for e in observed)
        if total_weight == 0:
            return 0.0
        return sum(e.score * e.weight for e in observed) / total_weight

    @property
    def physical_probability(self) -> float:
        """The evidence score expressed on the same 0-100 scale as the model."""
        return (self.physical_score + 1.0) / 2.0 * 100.0

    @property
    def disagreement(self) -> float:
        """Absolute gap between the model and the physical evidence, 0-100."""
        return abs(self.model_probability - self.physical_probability)

    @property
    def level(self) -> str:
        """agree | minor | major"""
        gap = self.disagreement
        if gap < 20:
            return "agree"
        if gap < 40:
            return "minor"
        return "major"

    def summary(self) -> str:
        """One sentence a non-specialist can act on."""
        gap = self.disagreement
        if self.level == "agree":
            return (
                f"The model ({self.model_probability:.0f}%) and the physical "
                f"evidence ({self.physical_probability:.0f}%) agree."
            )
        direction = (
            "HIGHER than" if self.model_probability > self.physical_probability
            else "LOWER than"
        )
        severity = "materially" if self.level == "major" else "somewhat"
        return (
            f"The model probability ({self.model_probability:.0f}%) is "
            f"{severity} {direction} the physical evidence supports "
            f"({self.physical_probability:.0f}%, a {gap:.0f} point gap). "
            f"Treat the model output with caution and read the evidence below."
        )


def check(features: Dict[str, float],
          model_probability: float,
          observation=None) -> ConsistencyReport:
    """
    Build the consistency report from the feature mapping.

    Each check uses standard operational thresholds, and any channel that was
    not actually observed is marked ``unobserved`` rather than being counted
    as evidence against convection - absence of measurement is not measurement
    of absence.
    """
    report = ConsistencyReport(model_probability=model_probability)

    # -- Instability (CAPE) ------------------------------------------------
    if features.get("nwp_observed"):
        cape = features.get("cape_j_kg", 0.0)
        if cape >= 1500:
            verdict, detail = "supports", f"CAPE {cape:.0f} J/kg - ample fuel for deep convection."
        elif cape >= 700:
            verdict, detail = "neutral", f"CAPE {cape:.0f} J/kg - marginal, storms possible but not favoured."
        else:
            verdict, detail = "opposes", f"CAPE {cape:.0f} J/kg - too little energy for deep convection."
        report.evidence.append(Evidence("Instability (CAPE)", verdict, detail, 1.4))

        # -- Inhibition (CIN) ---------------------------------------------
        cin = abs(features.get("cin_j_kg", 0.0))
        if cin >= 100:
            verdict, detail = "opposes", f"CIN {cin:.0f} J/kg - a strong cap suppresses convection without a trigger."
        elif cin >= 40:
            verdict, detail = "neutral", f"CIN {cin:.0f} J/kg - a weak cap that daytime heating may erode."
        else:
            verdict, detail = "supports", f"CIN {cin:.0f} J/kg - little inhibition, parcels can rise."
        report.evidence.append(Evidence("Inhibition (CIN)", verdict, detail, 1.0))

        # -- Lifted Index --------------------------------------------------
        li = features.get("lifted_index", 0.0)
        if li <= -4:
            verdict, detail = "supports", f"Lifted Index {li:+.1f} K - markedly unstable."
        elif li <= -1:
            verdict, detail = "neutral", f"Lifted Index {li:+.1f} K - weakly unstable."
        else:
            verdict, detail = "opposes", f"Lifted Index {li:+.1f} K - stable profile."
        report.evidence.append(Evidence("Lifted Index", verdict, detail, 1.1))
    else:
        report.evidence.append(Evidence(
            "Instability (CAPE)", "unobserved",
            "No NWP data for this run.", 1.4))

    # -- Satellite cloud tops ---------------------------------------------
    if features.get("satellite_observed"):
        deep = features.get("deep_convective_fraction", 0.0)
        bt_min = features.get("bt_min", 300.0)
        if deep >= 0.05 and bt_min <= config.BT_DEEP_CONVECTIVE_K:
            verdict = "supports"
            detail = (f"{deep:.1%} of the scene colder than 221 K - "
                      f"extensive deep convective cloud.")
        elif deep >= 0.01:
            verdict = "neutral"
            detail = f"{deep:.1%} deep convective cloud - scattered activity."
        else:
            verdict = "opposes"
            detail = "Little or no cloud colder than 221 K in the scene."
        report.evidence.append(Evidence("Satellite cloud tops", verdict, detail, 1.2))
    else:
        report.evidence.append(Evidence(
            "Satellite cloud tops", "unobserved",
            "No satellite observation for this run.", 1.2))

    # -- Radar -------------------------------------------------------------
    if features.get("radar_observed"):
        dbz = features.get("max_reflectivity_dbz", 0.0)
        convective = features.get("convective_fraction", 0.0)
        if dbz >= 45 or convective >= 0.02:
            verdict = "supports"
            detail = (f"Peak {dbz:.0f} dBZ with {convective:.2%} convective "
                      f"coverage - active cells in range.")
        elif dbz >= 30:
            verdict = "neutral"
            detail = f"Peak {dbz:.0f} dBZ - light precipitation only."
        else:
            verdict = "opposes"
            detail = f"Peak {dbz:.0f} dBZ - essentially no echo in range."
        report.evidence.append(Evidence("Radar reflectivity", verdict, detail, 1.3))
    else:
        report.evidence.append(Evidence(
            "Radar reflectivity", "unobserved",
            "No radar site in range is publishing.", 1.3))

    # -- Lightning ---------------------------------------------------------
    if features.get("lightning_observed"):
        strikes = features.get("lightning_strike_count", 0.0)
        if strikes >= 10:
            verdict = "supports"
            detail = f"{strikes:.0f} strikes in the last hour - electrically active."
        elif strikes >= 1:
            verdict = "neutral"
            detail = f"{strikes:.0f} strike(s) in the last hour - isolated activity."
        else:
            verdict = "opposes"
            detail = "No strikes detected in the last hour."
        report.evidence.append(Evidence("Lightning network", verdict, detail, 1.5))
    else:
        report.evidence.append(Evidence(
            "Lightning network", "unobserved",
            "No lightning network connected - this channel carries no "
            "information either way.", 1.5))

    # -- Diurnal timing ----------------------------------------------------
    if features.get("is_peak_hour"):
        report.evidence.append(Evidence(
            "Diurnal timing", "supports",
            "Within 14:00-18:00, the Indian thunderstorm maximum.", 0.6))
    elif features.get("is_night"):
        report.evidence.append(Evidence(
            "Diurnal timing", "opposes",
            "Overnight - surface heating is not driving convection.", 0.6))
    else:
        report.evidence.append(Evidence(
            "Diurnal timing", "neutral",
            "Outside the afternoon convective maximum.", 0.6))

    return report
