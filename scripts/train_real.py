"""
scripts/train_real.py
Train against OBSERVED lightning labels.

This is the script that turns the project from a working pipeline into a
skilful forecast system. It is the answer to ISSUE-021 in the register.

What you need first
-------------------
1. A lightning archive covering the period and region of interest, as CSV with
   columns ``time,lat,lon`` (and optionally ``type`` = CG or IC), placed in
   ``data/lightning/``. Sources: IITM/ISRO lightning network, Earth Networks
   ENTLN, Vaisala GLD360. All require institutional access; IMD is a
   subscriber to the commercial ones.

2. A matching archive of INSAT frames. Run ``scripts/collect_frames.py
   --watch`` through a storm season, or order historical L1B from MOSDAC.

How the label is defined
------------------------
A sample at time t is positive when at least ``--min-strikes`` strikes occur
within ``--radius`` km of the point during (t, t + ``--lead`` hours]. The
window is strictly FORWARD-LOOKING: including strikes at or before t would
leak the answer into the features and inflate every score.

Why the split is temporal
-------------------------
A random split puts frames from the same storm in both train and test, so the
model is scored on weather it has already seen. That inflates skill enormously
and is the single most common mistake in nowcasting papers. The last portion
in time is held out instead.

Usage
-----
    python scripts/train_real.py --city Delhi --lead 3 --radius 25
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import config
from utils import features as feat
from utils import metrics as vmetrics
from utils import optical_flow
from utils.datasources import lightning as lightning_src
from utils.datasources import mosdac
from utils.datasources.base import SourceStatus
from utils.predictor import ThunderstormPredictor


def build_dataset(city, lead_hours: float, radius_km: float,
                  min_strikes: int):
    """
    Assemble (X, y, timestamps) from the buffered frames and lightning archive.

    Returns None when either archive is too small, with an explanation - this
    script should tell you exactly what is missing rather than fabricating a
    dataset.
    """
    frames, timestamps = mosdac._buffered_frames("IR1")
    if len(frames) < 4:
        print(f"Only {len(frames)} INSAT frames are buffered. "
              f"At least 4 are needed, and a useful model needs thousands.\n"
              f"Run: python scripts/collect_frames.py --watch --interval 900")
        return None

    archive = lightning_src.fetch_local_archive(city.lat, city.lon, radius_km)
    if archive.status != SourceStatus.LIVE:
        print(f"No lightning archive: {archive.message}")
        return None

    strikes = archive.data["strikes"]
    if len(strikes) < 50:
        print(f"Only {len(strikes)} strikes in the archive. "
              f"Labels would be almost entirely negative.")
        return None

    print(f"Building samples from {len(frames)} frames and "
          f"{len(strikes)} strikes...")

    records, sample_times = [], []
    for i in range(1, len(frames)):
        flow = optical_flow.compute_optical_flow(frames[i - 1], frames[i])
        flow_features = optical_flow.extract_flow_features(flow, frames[i])

        # Lightning features must describe the PAST hour only, so they are
        # computed as of this sample's own time.
        strike_features = lightning_src.strike_features(
            strikes, city.lat, city.lon, radius_km, now=timestamps[i]
        )
        strike_features["lightning_observed"] = 1.0

        records.append(feat.build_features(
            frames[i], frames[i - 1], timestamps[: i + 1],
            flow_features=flow_features,
            fused_features=strike_features,
        ))
        sample_times.append(timestamps[i])

    X = feat.features_to_matrix(records)
    y = lightning_src.build_labels(
        strikes, sample_times, city.lat, city.lon,
        radius_km=radius_km, lead_hours=lead_hours, min_strikes=min_strikes,
    )

    print(f"  {X.shape[0]} samples, {X.shape[1]} features, "
          f"{y.mean():.1%} positive")
    return X, y, sample_times


def persistence_forecast(X, y, sample_times) -> np.ndarray:
    """
    Baseline: lightning in the last hour predicts lightning in the next few.

    Simple, and genuinely hard to beat at short lead times. Any model that
    cannot beat this is not adding value, and reporting skill without it is
    meaningless.
    """
    index = feat.FEATURE_NAMES.index("lightning_strike_count")
    counts = X[:, index]
    return np.clip(counts / max(counts.max(), 1.0), 0, 1) * 100.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Delhi")
    parser.add_argument("--lead", type=float, default=3.0,
                        help="forecast lead window in hours")
    parser.add_argument("--radius", type=float, default=25.0,
                        help="event radius in km")
    parser.add_argument("--min-strikes", type=int, default=1)
    parser.add_argument("--test-fraction", type=float, default=0.25)
    parser.add_argument("--output", default=str(config.MODEL_PATH))
    args = parser.parse_args()

    city = config.get_city(args.city)
    print(f"=== TRAINING ON OBSERVED DATA: {city.name} ===\n")

    dataset = build_dataset(city, args.lead, args.radius, args.min_strikes)
    if dataset is None:
        print("\nCannot train on observed data yet. See the messages above.")
        print("The demonstration model remains in place and is clearly "
              "labelled as such in the dashboard.")
        return 1

    X, y, sample_times = dataset

    if len(np.unique(y)) < 2:
        print("Labels are single-class; widen the radius or lead window.")
        return 1

    baseline = persistence_forecast(X, y, sample_times)
    cut = int(len(y) * (1 - args.test_fraction))
    baseline_test = baseline[cut:]

    predictor = ThunderstormPredictor()
    result = predictor.train(
        X, y,
        feature_names=feat.FEATURE_NAMES,
        training_data="observed",
        split_strategy="temporal",
        timestamps=sample_times,
        test_fraction=args.test_fraction,
        label_definition=(
            f"OBSERVED: at least {args.min_strikes} lightning strike(s) within "
            f"{args.radius:.0f} km during (t, t+{args.lead:.0f} h]. "
            f"Strictly forward-looking window."
        ),
        data_sources=[
            "INSAT-3D IR1 (MOSDAC public gallery)",
            "Lightning archive (data/lightning/)",
            "IMD DWR composites",
            "NWP convective parameters (Open-Meteo)",
        ],
        baseline_prob=baseline_test,
    )

    predictor.save_model(args.output)

    print(f"\nTrained on {result['n_train']} samples, "
          f"tested on {result['n_test']}.")
    validation = result["validation"]
    if "contingency" in validation:
        print("\n" + vmetrics.format_report(validation))
        if "csi_skill_over_baseline" in validation:
            skill = validation["csi_skill_over_baseline"]
            print(f"\nSkill over the persistence baseline: {skill:+.3f}")
            print("Positive means the model adds value over assuming "
                  "current conditions persist. That is the number to quote."
                  if skill > 0 else
                  "NEGATIVE - the model does not yet beat persistence. "
                  "Report this honestly and improve before claiming skill.")

    print(f"\nModel written to {args.output}")
    print(predictor.card.banner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
