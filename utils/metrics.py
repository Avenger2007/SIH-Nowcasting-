"""
utils/metrics.py
Forecast verification metrics for rare-event nowcasting.

Accuracy is the wrong metric for thunderstorm nowcasting. If storms occur on 5%
of samples, a model that always says "no storm" scores 95% accuracy and is
useless. Operational meteorology therefore verifies against the 2x2 contingency
table, and that is what IMD and WMO expect to see.

                      Observed yes    Observed no
    Forecast yes      hits (a)        false alarms (b)
    Forecast no       misses (c)      correct negatives (d)

Implemented here: POD, FAR, CSI, BIAS, HSS, PSS, plus Brier score and
reliability curves for the probabilistic output.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Sequence

import numpy as np


@dataclass
class ContingencyTable:
    """The 2x2 contingency table and every score derived from it."""

    hits: int
    false_alarms: int
    misses: int
    correct_negatives: int
    threshold: float

    # -- primary scores ----------------------------------------------------

    @property
    def total(self) -> int:
        return self.hits + self.false_alarms + self.misses + self.correct_negatives

    @property
    def pod(self) -> float:
        """Probability of Detection (hit rate). Perfect = 1."""
        denom = self.hits + self.misses
        return self.hits / denom if denom else float("nan")

    @property
    def far(self) -> float:
        """False Alarm Ratio. Perfect = 0."""
        denom = self.hits + self.false_alarms
        return self.false_alarms / denom if denom else float("nan")

    @property
    def pofd(self) -> float:
        """Probability of False Detection. Perfect = 0."""
        denom = self.false_alarms + self.correct_negatives
        return self.false_alarms / denom if denom else float("nan")

    @property
    def csi(self) -> float:
        """Critical Success Index (threat score). Perfect = 1."""
        denom = self.hits + self.misses + self.false_alarms
        return self.hits / denom if denom else float("nan")

    @property
    def bias(self) -> float:
        """Frequency bias. 1 = unbiased, >1 = over-forecasting."""
        denom = self.hits + self.misses
        return (self.hits + self.false_alarms) / denom if denom else float("nan")

    @property
    def hss(self) -> float:
        """Heidke Skill Score against random chance. Perfect = 1."""
        a, b, c, d = self.hits, self.false_alarms, self.misses, self.correct_negatives
        n = self.total
        if n == 0:
            return float("nan")
        expected = ((a + c) * (a + b) + (b + d) * (c + d)) / n
        denom = n - expected
        return (a + d - expected) / denom if denom else float("nan")

    @property
    def pss(self) -> float:
        """Peirce Skill Score (Hanssen-Kuipers discriminant). Perfect = 1."""
        pod, pofd = self.pod, self.pofd
        if np.isnan(pod) or np.isnan(pofd):
            return float("nan")
        return pod - pofd

    @property
    def accuracy(self) -> float:
        """Included only so it can be shown next to how misleading it is."""
        return (self.hits + self.correct_negatives) / self.total if self.total else float("nan")

    @property
    def base_rate(self) -> float:
        """Observed event frequency - the number that makes accuracy a lie."""
        denom = self.total
        return (self.hits + self.misses) / denom if denom else float("nan")

    def to_dict(self) -> Dict[str, float]:
        d = asdict(self)
        d.update({
            "pod": self.pod,
            "far": self.far,
            "pofd": self.pofd,
            "csi": self.csi,
            "bias": self.bias,
            "hss": self.hss,
            "pss": self.pss,
            "accuracy": self.accuracy,
            "base_rate": self.base_rate,
            "total": self.total,
        })
        return d


def contingency(y_true: Sequence[int],
                y_prob: Sequence[float],
                threshold: float = 0.5) -> ContingencyTable:
    """Build the contingency table at a probability threshold."""
    y_true = np.asarray(y_true).astype(int).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()
    if y_prob.max(initial=0.0) > 1.0:  # tolerate 0-100 input
        y_prob = y_prob / 100.0

    forecast = y_prob >= threshold
    observed = y_true == 1

    return ContingencyTable(
        hits=int(np.sum(forecast & observed)),
        false_alarms=int(np.sum(forecast & ~observed)),
        misses=int(np.sum(~forecast & observed)),
        correct_negatives=int(np.sum(~forecast & ~observed)),
        threshold=float(threshold),
    )


def brier_score(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """Mean squared error of the probability forecast. Lower is better."""
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()
    if y_prob.max(initial=0.0) > 1.0:
        y_prob = y_prob / 100.0
    return float(np.mean((y_prob - y_true) ** 2))


def brier_skill_score(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """
    Brier score relative to climatology. Positive = better than always
    forecasting the base rate. This is the honest headline number.
    """
    y_true = np.asarray(y_true, dtype=float).ravel()
    bs = brier_score(y_true, y_prob)
    climatology = float(np.mean(y_true))
    bs_ref = float(np.mean((climatology - y_true) ** 2))
    return 1.0 - bs / bs_ref if bs_ref > 0 else float("nan")


def roc_curve(y_true: Sequence[int],
              y_prob: Sequence[float],
              n_thresholds: int = 51) -> Dict[str, List[float]]:
    """ROC curve built from the contingency table at many thresholds."""
    thresholds = np.linspace(0.0, 1.0, n_thresholds)
    pod, pofd = [], []
    for t in thresholds:
        table = contingency(y_true, y_prob, threshold=t)
        pod.append(table.pod)
        pofd.append(table.pofd)
    return {
        "thresholds": thresholds.tolist(),
        "pod": pod,
        "pofd": pofd,
    }


def auc(y_true: Sequence[int], y_prob: Sequence[float]) -> float:
    """
    Area under the ROC curve, computed exactly.

    This uses the Mann-Whitney U identity: the AUC equals the probability that
    a randomly chosen positive is ranked above a randomly chosen negative.

    It deliberately does NOT integrate the sampled ROC curve. Doing that
    understates the area, because a coarse threshold grid produces many points
    sharing the same false-alarm rate; once they are sorted by x, the
    trapezoid rule integrates straight through the vertical segment and
    discards it. Perfectly separable data scored 0.833 instead of 1.0 that
    way. The rank formulation has no such failure mode and handles ties by
    averaging them, which is the standard convention.
    """
    y_true = np.asarray(y_true).astype(int).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()
    if y_prob.max(initial=0.0) > 1.0:
        y_prob = y_prob / 100.0

    n_pos = int(np.sum(y_true == 1))
    n_neg = int(np.sum(y_true == 0))
    if n_pos == 0 or n_neg == 0:
        return float("nan")

    # Average ranks, so tied scores contribute 0.5 each.
    order = np.argsort(y_prob, kind="mergesort")
    ranks = np.empty(len(y_prob), dtype=float)
    ranks[order] = np.arange(1, len(y_prob) + 1, dtype=float)

    sorted_prob = y_prob[order]
    i = 0
    while i < len(sorted_prob):
        j = i
        while j + 1 < len(sorted_prob) and sorted_prob[j + 1] == sorted_prob[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1

    rank_sum_positive = float(np.sum(ranks[y_true == 1]))
    return (rank_sum_positive - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def reliability_curve(y_true: Sequence[int],
                      y_prob: Sequence[float],
                      n_bins: int = 10) -> Dict[str, List[float]]:
    """
    Reliability (calibration) curve: of the times we said 70%, did it happen
    70% of the time? A confident-but-wrong model shows up here immediately.
    """
    y_true = np.asarray(y_true, dtype=float).ravel()
    y_prob = np.asarray(y_prob, dtype=float).ravel()
    if y_prob.max(initial=0.0) > 1.0:
        y_prob = y_prob / 100.0

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    forecast_prob, observed_freq, counts = [], [], []

    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        n = int(mask.sum())
        counts.append(n)
        if n:
            forecast_prob.append(float(y_prob[mask].mean()))
            observed_freq.append(float(y_true[mask].mean()))
        else:
            forecast_prob.append(float((lo + hi) / 2))
            observed_freq.append(float("nan"))

    return {
        "forecast_probability": forecast_prob,
        "observed_frequency": observed_freq,
        "counts": counts,
    }


def find_best_threshold(y_true: Sequence[int],
                        y_prob: Sequence[float],
                        optimise: str = "csi",
                        n_thresholds: int = 101) -> Dict[str, float]:
    """
    Pick the operating threshold that maximises a chosen score.

    For warnings, CSI or PSS is the usual target: it balances catching storms
    against crying wolf. The default 0.5 is almost never the right choice for a
    rare event.
    """
    best = {"threshold": 0.5, "score": -np.inf}
    for t in np.linspace(0.01, 0.99, n_thresholds):
        table = contingency(y_true, y_prob, threshold=t)
        score = getattr(table, optimise)
        if np.isfinite(score) and score > best["score"]:
            best = {"threshold": float(t), "score": float(score)}
    return best


def full_report(y_true: Sequence[int],
                y_prob: Sequence[float],
                threshold: Optional[float] = None,
                baseline_prob: Optional[Sequence[float]] = None) -> Dict:
    """
    Produce the complete verification package.

    Args:
        y_true: observed binary outcomes.
        y_prob: forecast probabilities.
        threshold: operating threshold. If None, the CSI-optimal one is used.
        baseline_prob: optional competing forecast (e.g. Eulerian persistence)
            so that skill can be reported *relative to a baseline*, which is
            the only way a nowcasting result means anything.
    """
    if threshold is None:
        threshold = find_best_threshold(y_true, y_prob, "csi")["threshold"]

    table = contingency(y_true, y_prob, threshold)
    report = {
        "contingency": table.to_dict(),
        "brier_score": brier_score(y_true, y_prob),
        "brier_skill_score": brier_skill_score(y_true, y_prob),
        "auc": auc(y_true, y_prob),
        "reliability": reliability_curve(y_true, y_prob),
        "roc": roc_curve(y_true, y_prob),
        "operating_threshold": float(threshold),
    }

    if baseline_prob is not None:
        base_table = contingency(y_true, baseline_prob, threshold)
        report["baseline"] = {
            "contingency": base_table.to_dict(),
            "brier_score": brier_score(y_true, baseline_prob),
            "auc": auc(y_true, baseline_prob),
        }
        # Skill of the model over the baseline, in CSI terms.
        model_csi, base_csi = table.csi, base_table.csi
        if np.isfinite(model_csi) and np.isfinite(base_csi) and base_csi < 1:
            report["csi_skill_over_baseline"] = float(
                (model_csi - base_csi) / (1.0 - base_csi)
            )

    return report


def format_report(report: Dict) -> str:
    """Render a verification report as a readable markdown table."""
    c = report["contingency"]
    lines = [
        "| Metric | Value | Perfect |",
        "|---|---|---|",
        f"| Probability of Detection (POD) | {c['pod']:.3f} | 1.000 |",
        f"| False Alarm Ratio (FAR) | {c['far']:.3f} | 0.000 |",
        f"| Critical Success Index (CSI) | {c['csi']:.3f} | 1.000 |",
        f"| Frequency Bias | {c['bias']:.3f} | 1.000 |",
        f"| Heidke Skill Score (HSS) | {c['hss']:.3f} | 1.000 |",
        f"| Peirce Skill Score (PSS) | {c['pss']:.3f} | 1.000 |",
        f"| ROC AUC | {report['auc']:.3f} | 1.000 |",
        f"| Brier Score | {report['brier_score']:.4f} | 0.000 |",
        f"| Brier Skill Score | {report['brier_skill_score']:.3f} | 1.000 |",
        "",
        f"Operating threshold: {report['operating_threshold']:.2f}  ",
        f"Observed base rate: {c['base_rate']:.3f}  ",
        f"Hits {c['hits']} / False alarms {c['false_alarms']} / "
        f"Misses {c['misses']} / Correct negatives {c['correct_negatives']}",
    ]
    if "csi_skill_over_baseline" in report:
        lines.append(
            f"\n**CSI skill over persistence baseline: "
            f"{report['csi_skill_over_baseline']:+.3f}**"
        )
    return "\n".join(lines)
