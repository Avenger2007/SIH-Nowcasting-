"""
scripts/live_test.py
End-to-end smoke test against LIVE data sources.

Run this to prove the pipeline works with real observations:

    python scripts/live_test.py Delhi
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import config
from utils import features as feat
from utils import llm_alert, optical_flow
from utils.datasources import fusion
from utils.predictor import ThunderstormPredictor


def main(city_name: str = "Delhi") -> int:
    city = config.get_city(city_name)
    print(f"=== LIVE NOWCAST TEST: {city.name} "
          f"({city.lat:.3f}, {city.lon:.3f}) ===\n")

    # 1. Fuse every data source.
    print("[1/5] Fetching satellite, radar, lightning and model data...")
    observation = fusion.fuse(city.lat, city.lon, city.name)

    for row in observation.provenance():
        flag = "LIVE " if row["is_observation"] else "  -  "
        print(f"   {flag} {row['leg']:<10} {row['status']:<18} "
              f"{row['latency_ms']:>7.0f} ms  {row['source'][:52]}")
    print(f"\n   {observation.confidence_note()}\n")

    # 2. Optical flow on the satellite sequence.
    print("[2/5] Computing cloud motion...")
    frames, timestamps = fusion.get_satellite_frames(observation)
    if len(frames) < 2:
        print("   Not enough frames for motion.")
        return 1

    satellite = observation.sources["satellite"]
    motion_available = satellite.data.get("motion_available", False)

    flow = optical_flow.compute_optical_flow(frames[-2], frames[-1])
    flow_features = optical_flow.extract_flow_features(flow, frames[-1])
    print(f"   Mean motion {flow_features['flow_magnitude_mean']:.2f} px/frame, "
          f"bearing {flow_features['flow_direction_mean']:.0f} deg "
          f"(motion_available={motion_available})")

    # 3. Build the feature mapping.
    print("\n[3/5] Building features...")
    features = feat.build_features(
        frames[-1], frames[-2], timestamps,
        flow_features=flow_features,
        fused_features=observation.features,
    )
    print(f"   {len(features)} features assembled")
    print(f"   Coldest cloud top   : {features['bt_min']:.1f} K")
    print(f"   Deep convective frac: {features['deep_convective_fraction']:.2%}")
    print(f"   CAPE                : {features['cape_j_kg']:.0f} J/kg")
    print(f"   Lifted Index        : {features['lifted_index']:+.1f} K")
    print(f"   Peak reflectivity   : {features['max_reflectivity_dbz']:.0f} dBZ")
    print(f"   Lightning observed  : {bool(features['lightning_observed'])}")

    # 4. Predict.
    print("\n[4/5] Running the model...")
    predictor = ThunderstormPredictor().load_model()
    prediction = predictor.predict_single(features)
    print(f"   Probability: {prediction['thunderstorm_probability']:.1f}%  "
          f"({prediction['risk_level']})")
    print(f"   {prediction['banner']}")
    if prediction["out_of_distribution"]:
        print(f"   {len(prediction['out_of_distribution'])} feature(s) outside "
              f"the training distribution:")
        for item in prediction["out_of_distribution"][:5]:
            print(f"      {item['feature']}: {item['value']:.2f} "
                  f"(z={item['z_score']:.1f})")

    # 5. Alert.
    print("\n[5/5] Generating the alert...")
    alert = llm_alert.generate_alert(prediction, city.name, observation)
    print(f"   [{alert['method']}] {alert['text']}")
    if alert["note"]:
        print(f"   note: {alert['note']}")

    # Nowcast frames.
    nowcasts, _ = optical_flow.nowcast_sequence(frames)
    print(f"\n   Generated {len(nowcasts)} nowcast frames "
          f"(+1h to +6h), shape {nowcasts[0].shape}")

    print("\n=== PIPELINE COMPLETED ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "Delhi"))
