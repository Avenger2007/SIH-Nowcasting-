"""
utils/features.py
Feature engineering for thunderstorm and lightning nowcasting.

Changes from the original:

  * Everything works in KELVIN. The old code compared raw 8-bit display values
    against ``img < 150``, which is meaningless for calibrated INSAT data.
  * ``build_feature_vector`` returned a tuple while its annotation promised an
    ndarray, and callers depended on the alphabetical ordering of a dict. It
    now returns a NAMED MAPPING and the model aligns it by name.
  * FEATURE_NAMES is the single canonical list, shared by training and
    inference so the two can never drift apart.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Sequence

import cv2
import numpy as np

import config
from utils.calibration import cloud_top_height_km, convective_mask, ensure_kelvin


# --------------------------------------------------------------------------
# Canonical feature list
# --------------------------------------------------------------------------
# The order here is the model's column order. Adding a feature means retraining;
# the FeatureContract makes that failure loud rather than silent.

SATELLITE_FEATURES = [
    "bt_mean", "bt_std", "bt_min", "bt_max", "bt_p05", "bt_p25",
    "bt_gradient_mean", "bt_gradient_std",
    "cooling_rate_mean", "cooling_rate_max", "cooling_rate_min",
    "cooling_rate_std",
    "cold_cloud_fraction", "deep_convective_fraction", "overshoot_fraction",
    "rapid_cooling_fraction",
    "cloud_top_height_max_km", "cloud_top_height_mean_km",
    "texture_mean", "texture_std", "texture_max",
    "gradient_mean", "gradient_std", "gradient_max",
    "laplacian_mean", "laplacian_std",
    "cloud_count", "max_cloud_area", "mean_cloud_area",
    "total_cloud_fraction", "cloud_area_std", "max_cloud_compactness",
]

FLOW_FEATURES = [
    "flow_magnitude_mean", "flow_magnitude_std", "flow_magnitude_max",
    "flow_direction_mean", "flow_direction_std",
    "convergence_mean", "convergence_max", "convergence_min",
    "convergence_std", "convergence_in_cold_cloud",
]

TEMPORAL_FEATURES = [
    "hour_of_day", "hour_sin", "hour_cos", "month",
    "is_afternoon", "is_evening", "is_night", "is_monsoon", "is_peak_hour",
]

NWP_FEATURES = [
    "cape_j_kg", "cin_j_kg", "lifted_index", "k_index", "total_totals",
    "precipitable_water_mm", "deep_layer_shear_ms", "lapse_rate_850_500",
    "nwp_observed",
]

RADAR_FEATURES = [
    "max_reflectivity_dbz", "mean_reflectivity_dbz", "echo_coverage_fraction",
    "convective_fraction", "intense_core_fraction", "reflectivity_std",
    "radar_station_count", "radar_observed",
]

LIGHTNING_FEATURES = [
    "lightning_strike_count", "lightning_cg_count", "lightning_ic_count",
    "lightning_ic_cg_ratio", "lightning_density_per_1000km2",
    "lightning_rate_15min", "lightning_rate_30min", "lightning_jump_ratio",
    "lightning_nearest_km", "lightning_observed",
]

SURFACE_FEATURES = [
    "temperature", "humidity", "pressure", "dew_point_depression",
    "wind_speed", "wind_deg", "cloud_cover", "visibility", "surface_observed",
]

FEATURE_NAMES: List[str] = (
    SATELLITE_FEATURES
    + FLOW_FEATURES
    + TEMPORAL_FEATURES
    + NWP_FEATURES
    + RADAR_FEATURES
    + LIGHTNING_FEATURES
    + SURFACE_FEATURES
    + ["satellite_observed"]
)

FEATURE_GROUPS = {
    "Satellite (INSAT-3D IR)": SATELLITE_FEATURES,
    "Cloud motion (optical flow)": FLOW_FEATURES,
    "Temporal / diurnal": TEMPORAL_FEATURES,
    "NWP convective parameters": NWP_FEATURES,
    "Radar (IMD DWR)": RADAR_FEATURES,
    "Lightning network": LIGHTNING_FEATURES,
    "Surface observations": SURFACE_FEATURES,
}


# --------------------------------------------------------------------------
# Satellite features
# --------------------------------------------------------------------------

def extract_cooling_features(bt_now: np.ndarray,
                             bt_prev: np.ndarray,
                             minutes: float = config.SATELLITE_INTERVAL_MIN
                             ) -> Dict[str, float]:
    """
    Cloud-top cooling in K/min - the single most useful IR convective signal.

    A cloud top that is cooling rapidly is a cloud that is growing vertically.
    Sustained cooling of ~0.25 K/min or more marks vigorous convection likely
    to produce lightning within the hour.
    """
    now = ensure_kelvin(bt_now)
    prev = ensure_kelvin(bt_prev)

    # Positive = cooling = growing.
    cooling = (prev - now) / max(minutes, 1e-6)

    cold = convective_mask(now, config.BT_CONVECTIVE_K)
    deep = convective_mask(now, config.BT_DEEP_CONVECTIVE_K)
    overshoot = convective_mask(now, config.BT_OVERSHOOT_K)
    heights = cloud_top_height_km(now)

    sobel_x = cv2.Sobel(now, cv2.CV_32F, 1, 0, ksize=3)

    return {
        "bt_mean": float(np.mean(now)),
        "bt_std": float(np.std(now)),
        "bt_min": float(np.min(now)),
        "bt_max": float(np.max(now)),
        "bt_p05": float(np.percentile(now, 5)),
        "bt_p25": float(np.percentile(now, 25)),
        "bt_gradient_mean": float(np.mean(np.abs(sobel_x))),
        "bt_gradient_std": float(np.std(sobel_x)),
        "cooling_rate_mean": float(np.mean(cooling)),
        "cooling_rate_max": float(np.max(cooling)),
        "cooling_rate_min": float(np.min(cooling)),
        "cooling_rate_std": float(np.std(cooling)),
        "cold_cloud_fraction": float(np.mean(cold)),
        "deep_convective_fraction": float(np.mean(deep)),
        "overshoot_fraction": float(np.mean(overshoot)),
        "rapid_cooling_fraction": float(
            np.mean(cooling > config.RAPID_COOLING_K_PER_MIN)
        ),
        "cloud_top_height_max_km": float(np.max(heights)),
        "cloud_top_height_mean_km": float(np.mean(heights[cold])) if cold.any() else 0.0,
    }


def extract_texture_features(bt: np.ndarray) -> Dict[str, float]:
    """
    Texture. Convective tops are lumpy; stratiform cloud and clear air are not.
    """
    field = ensure_kelvin(bt)

    kernel = 5
    local_mean = cv2.blur(field, (kernel, kernel))
    local_sq = cv2.blur(field ** 2, (kernel, kernel))
    local_std = np.sqrt(np.maximum(local_sq - local_mean ** 2, 0))

    grad_x = cv2.Sobel(field, cv2.CV_32F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(field, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.hypot(grad_x, grad_y)
    laplacian = np.abs(cv2.Laplacian(field, cv2.CV_32F))

    return {
        "texture_mean": float(np.mean(local_std)),
        "texture_std": float(np.std(local_std)),
        "texture_max": float(np.max(local_std)),
        "gradient_mean": float(np.mean(gradient)),
        "gradient_std": float(np.std(gradient)),
        "gradient_max": float(np.max(gradient)),
        "laplacian_mean": float(np.mean(laplacian)),
        "laplacian_std": float(np.std(laplacian)),
    }


def extract_cloud_objects(bt: np.ndarray) -> Dict[str, float]:
    """
    Cloud-object statistics.

    Compactness (4*pi*area / perimeter^2) separates a compact, vigorous cell
    from a sprawling decaying anvil that covers the same area.
    """
    field = ensure_kelvin(bt)
    binary = convective_mask(field, config.BT_CONVECTIVE_K).astype(np.uint8) * 255

    contours, _ = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return {
            "cloud_count": 0.0, "max_cloud_area": 0.0, "mean_cloud_area": 0.0,
            "total_cloud_fraction": 0.0, "cloud_area_std": 0.0,
            "max_cloud_compactness": 0.0,
        }

    areas = np.array([cv2.contourArea(c) for c in contours], dtype=float)
    largest = contours[int(np.argmax(areas))]
    perimeter = cv2.arcLength(largest, True)
    compactness = (
        4 * np.pi * areas.max() / (perimeter ** 2) if perimeter > 0 else 0.0
    )

    return {
        "cloud_count": float(len(contours)),
        "max_cloud_area": float(areas.max()),
        "mean_cloud_area": float(areas.mean()),
        "total_cloud_fraction": float(areas.sum() / field.size),
        "cloud_area_std": float(areas.std()),
        "max_cloud_compactness": float(min(compactness, 1.0)),
    }


def extract_temporal_features(timestamps: Sequence[datetime]) -> Dict[str, float]:
    """
    Diurnal and seasonal context.

    Thunderstorms over India peak in the late afternoon as surface heating
    erodes the cap, so hour-of-day carries real signal. It is encoded
    cyclically as well as raw, because hour 23 and hour 0 are adjacent and a
    tree should not have to learn that from scratch.
    """
    if not timestamps:
        latest = datetime.utcnow()
    else:
        latest = timestamps[-1]

    hour, month = latest.hour, latest.month

    return {
        "hour_of_day": float(hour),
        "hour_sin": float(np.sin(2 * np.pi * hour / 24)),
        "hour_cos": float(np.cos(2 * np.pi * hour / 24)),
        "month": float(month),
        "is_afternoon": float(12 <= hour <= 18),
        "is_evening": float(18 < hour <= 21),
        "is_night": float(hour >= 21 or hour <= 5),
        "is_monsoon": float(6 <= month <= 9),
        "is_peak_hour": float(14 <= hour <= 18),
    }


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------

def build_features(bt_now: np.ndarray,
                   bt_prev: np.ndarray,
                   timestamps: Sequence[datetime],
                   flow_features: Optional[Dict[str, float]] = None,
                   fused_features: Optional[Dict[str, float]] = None,
                   interval_minutes: float = config.SATELLITE_INTERVAL_MIN,
                   ) -> Dict[str, float]:
    """
    Build the complete NAMED feature mapping.

    Returns a dict, not an array. The model aligns it against its own contract
    by name, so nothing here depends on ordering.

    Args:
        bt_now, bt_prev: consecutive IR rasters (Kelvin or 8-bit counts;
            converted automatically).
        timestamps: frame times, most recent last.
        flow_features: from utils.optical_flow.extract_flow_features.
        fused_features: from utils.datasources.fusion - the radar, lightning,
            NWP and surface legs.
    """
    features: Dict[str, float] = {}

    features.update(extract_cooling_features(bt_now, bt_prev, interval_minutes))
    features.update(extract_texture_features(bt_now))
    features.update(extract_cloud_objects(bt_now))
    features.update(extract_temporal_features(timestamps))

    if flow_features:
        features.update(flow_features)
    else:
        features.update({name: 0.0 for name in FLOW_FEATURES})

    if fused_features:
        features.update(fused_features)

    # Guarantee the contract is fully populated: any leg that did not report
    # gets an explicit zero rather than a KeyError at predict time.
    for name in FEATURE_NAMES:
        features.setdefault(name, 0.0)

    return {name: float(features[name]) for name in FEATURE_NAMES}


def features_to_matrix(records: Sequence[Dict[str, float]]) -> np.ndarray:
    """Stack feature dicts into a matrix in canonical FEATURE_NAMES order."""
    return np.array(
        [[record.get(name, 0.0) for name in FEATURE_NAMES] for record in records],
        dtype=np.float32,
    )


def describe_feature(name: str) -> str:
    """Plain-English description, used for UI tooltips."""
    return FEATURE_DESCRIPTIONS.get(name, name.replace("_", " ").capitalize())


FEATURE_DESCRIPTIONS: Dict[str, str] = {
    "bt_min": "Coldest cloud-top brightness temperature (K). Lower means a taller, more vigorous storm.",
    "cold_cloud_fraction": "Fraction of the scene colder than 241 K - cumulonimbus anvil coverage.",
    "deep_convective_fraction": "Fraction colder than 221 K - deep convection likely to produce lightning.",
    "overshoot_fraction": "Fraction colder than 205 K - overshooting tops, a severe-storm signature.",
    "cooling_rate_max": "Fastest cloud-top cooling (K/min). Sustained cooling means vertical growth.",
    "rapid_cooling_fraction": "Fraction of the scene cooling faster than 0.25 K/min.",
    "cloud_top_height_max_km": "Highest retrieved cloud top (km), from the IR temperature.",
    "max_cloud_compactness": "Shape of the largest cell. Compact means vigorous; sprawling means decaying.",
    "cape_j_kg": "Convective Available Potential Energy (J/kg) - the fuel available to a storm.",
    "cin_j_kg": "Convective Inhibition (J/kg) - the cap holding convection down.",
    "lifted_index": "Lifted Index (K). Negative means the atmosphere is unstable.",
    "k_index": "K-index. Above ~30 indicates thunderstorm potential.",
    "total_totals": "Total Totals index. Above ~50 indicates severe potential.",
    "deep_layer_shear_ms": "10 m to 500 hPa wind shear (m/s). Organises storms and extends their life.",
    "precipitable_water_mm": "Total column moisture (mm) available to rain out.",
    "max_reflectivity_dbz": "Peak radar reflectivity (dBZ). Above 50 dBZ suggests hail or intense rain.",
    "convective_fraction": "Radar area above 35 dBZ - convective core coverage.",
    "intense_core_fraction": "Radar area above 50 dBZ - intense cores.",
    "radar_station_count": "How many DWR sites contributed to this composite.",
    "lightning_strike_count": "Strikes detected within the analysis radius in the last hour.",
    "lightning_jump_ratio": "Recent strike rate versus the preceding period. A jump often precedes severe weather.",
    "lightning_ic_cg_ratio": "Intracloud to cloud-to-ground ratio - rises as a storm intensifies.",
    "lightning_observed": "1 if a lightning network was actually connected, 0 if the channel is unobserved.",
    "convergence_in_cold_cloud": "Low-level convergence beneath cold cloud tops - where new cells form.",
    "dew_point_depression": "Temperature minus dew point (K). Small values mean a moist boundary layer.",
    "is_peak_hour": "1 during 14:00-18:00, the Indian thunderstorm maximum.",
    "is_monsoon": "1 during June-September.",
}
