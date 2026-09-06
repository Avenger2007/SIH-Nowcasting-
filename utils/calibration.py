"""
utils/calibration.py
Brightness-temperature calibration for infrared satellite imagery.

The original pipeline compared raw 8-bit pixel values against a magic constant
(``img < 150``). That is meaningless the moment real INSAT-3D data arrives,
because a calibrated product carries Kelvin, not display counts, and different
browse products use different stretches.

Every physical threshold in this project is therefore expressed in KELVIN, and
rasters are converted to Kelvin exactly once, at ingestion.
"""

from __future__ import annotations

import numpy as np

import config


def counts_to_kelvin(counts: np.ndarray,
                     bt_min: float = config.BT_MIN_K,
                     bt_max: float = config.BT_MAX_K,
                     inverted: bool = True) -> np.ndarray:
    """
    Convert 8-bit browse-image counts to brightness temperature in Kelvin.

    Args:
        counts: array of 0-255 display values.
        bt_min: temperature mapped to the cold end of the stretch.
        bt_max: temperature mapped to the warm end of the stretch.
        inverted: True for the usual IR convention where BRIGHT pixels are COLD
            cloud tops. Set False for products where bright means warm.

    Returns:
        Float32 array of brightness temperatures in Kelvin.
    """
    scaled = np.asarray(counts, dtype=np.float32) / 255.0
    if inverted:
        scaled = 1.0 - scaled
    return (bt_min + scaled * (bt_max - bt_min)).astype(np.float32)


def kelvin_to_counts(kelvin: np.ndarray,
                     bt_min: float = config.BT_MIN_K,
                     bt_max: float = config.BT_MAX_K,
                     inverted: bool = True) -> np.ndarray:
    """Inverse of :func:`counts_to_kelvin`, for display and optical flow."""
    scaled = (np.asarray(kelvin, dtype=np.float32) - bt_min) / (bt_max - bt_min)
    scaled = np.clip(scaled, 0.0, 1.0)
    if inverted:
        scaled = 1.0 - scaled
    return (scaled * 255.0).astype(np.uint8)


def is_kelvin(array: np.ndarray) -> bool:
    """
    Heuristic: decide whether an array already holds Kelvin.

    Physical IR brightness temperatures for Earth sit roughly in 180-330 K,
    which never overlaps the 0-255 count range in a way that matters here:
    a count raster has a minimum below 180 in practice, a Kelvin raster does not.
    """
    arr = np.asarray(array)
    if arr.dtype == np.uint8:
        return False
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return False
    return bool(finite.min() >= 150.0 and finite.max() <= 400.0)


def ensure_kelvin(array: np.ndarray, **kwargs) -> np.ndarray:
    """Return the raster in Kelvin, converting from counts only if needed."""
    if is_kelvin(array):
        return np.asarray(array, dtype=np.float32)
    return counts_to_kelvin(array, **kwargs)


def convective_mask(bt_kelvin: np.ndarray,
                    threshold_k: float = config.BT_CONVECTIVE_K) -> np.ndarray:
    """Boolean mask of pixels colder than a convective threshold."""
    return np.asarray(bt_kelvin, dtype=np.float32) < threshold_k


def cloud_top_height_km(bt_kelvin: np.ndarray,
                        surface_temp_k: float = 300.0,
                        lapse_rate_k_per_km: float = 6.5) -> np.ndarray:
    """
    First-order cloud-top height from brightness temperature.

    Assumes a moist-adiabatic standard atmosphere. This is the classic
    IR height retrieval: crude above the tropopause, but useful as a feature
    and honest about what it is.
    """
    bt = np.asarray(bt_kelvin, dtype=np.float32)
    height = (surface_temp_k - bt) / lapse_rate_k_per_km
    return np.clip(height, 0.0, 20.0)
