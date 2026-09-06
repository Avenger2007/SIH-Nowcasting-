"""
utils/optical_flow.py
Cloud motion estimation and Lagrangian-persistence nowcasting.

This module was already sound in the original project - Farneback dense flow
plus semi-Lagrangian advection is the standard operational nowcasting method
and it was implemented correctly. The changes here are:

  * flow is computed on a CONTRAST-NORMALISED field, so a cold-topped storm
    does not dominate the estimate purely through its brightness;
  * a persistence BASELINE is provided, because a nowcast that cannot beat
    "assume nothing changes" has no skill worth reporting;
  * convergence is measured where it matters - beneath cold cloud - rather
    than averaged over the whole scene including clear air.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

import config
from utils.calibration import convective_mask, ensure_kelvin, kelvin_to_counts


def _to_flow_input(field: np.ndarray) -> np.ndarray:
    """
    Prepare a raster for Farneback.

    OpenCV wants 8-bit single-channel. Kelvin fields are normalised over the
    scene's own range so that flow tracks STRUCTURE rather than absolute
    temperature, which makes the estimate stable across day/night transitions.
    """
    array = np.asarray(field)

    if array.ndim == 3:
        array = cv2.cvtColor(array, cv2.COLOR_BGR2GRAY)

    if array.dtype == np.uint8:
        return array

    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return np.zeros(array.shape, dtype=np.uint8)

    low, high = np.percentile(finite, [1, 99])
    if high - low < 1e-6:
        return np.zeros(array.shape, dtype=np.uint8)

    scaled = np.clip((array - low) / (high - low), 0, 1)
    # Invert so cold cloud is bright: features to track are then high-valued.
    return ((1.0 - scaled) * 255).astype(np.uint8)


def compute_optical_flow(prev_field: np.ndarray,
                         next_field: np.ndarray) -> np.ndarray:
    """
    Dense Farneback optical flow between two frames.

    Returns an (H, W, 2) array of pixel displacements. No training required -
    this is pure computation, which is why the whole system runs on a CPU.
    """
    prev_gray = _to_flow_input(prev_field)
    next_gray = _to_flow_input(next_field)

    return cv2.calcOpticalFlowFarneback(
        prev_gray, next_gray, None,
        pyr_scale=0.5,
        levels=3,
        winsize=21,      # widened: satellite cloud fields are smooth
        iterations=3,
        poly_n=5,
        poly_sigma=1.2,
        flags=0,
    )


def advect(field: np.ndarray,
           flow: np.ndarray,
           steps: float = 1.0) -> np.ndarray:
    """
    Move a field along the flow vectors - semi-Lagrangian advection.

    This is Lagrangian persistence: the assumption that cloud features keep
    moving as they have been moving. It is the workhorse of 0-2 hour
    nowcasting and remains hard to beat at short lead times.

    Note the sign: to find what arrives at pixel p after advection, sample the
    source location p - flow*steps, so the remap uses the NEGATIVE flow.
    """
    height, width = field.shape[:2]

    grid_x, grid_y = np.meshgrid(
        np.arange(width, dtype=np.float32),
        np.arange(height, dtype=np.float32),
    )

    map_x = (grid_x - flow[..., 0] * steps).astype(np.float32)
    map_y = (grid_y - flow[..., 1] * steps).astype(np.float32)

    return cv2.remap(
        field.astype(np.float32), map_x, map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def flow_magnitude(flow: np.ndarray) -> np.ndarray:
    return np.hypot(flow[..., 0], flow[..., 1])


def flow_direction(flow: np.ndarray) -> np.ndarray:
    """Direction in degrees, meteorological convention (0 = from north)."""
    return np.degrees(np.arctan2(flow[..., 0], -flow[..., 1])) % 360.0


def extract_flow_features(flow: np.ndarray,
                          bt_field: Optional[np.ndarray] = None
                          ) -> Dict[str, float]:
    """
    Statistical flow features.

    ``convergence_in_cold_cloud`` is the meteorologically meaningful one:
    low-level convergence collocated with cold cloud top is where new cells
    develop. Averaging convergence over the whole scene - as the original code
    did - dilutes that signal with clear-air noise.
    """
    magnitude = flow_magnitude(flow)
    direction = flow_direction(flow)

    du_dx = cv2.Sobel(flow[..., 0], cv2.CV_32F, 1, 0, ksize=3)
    dv_dy = cv2.Sobel(flow[..., 1], cv2.CV_32F, 0, 1, ksize=3)
    convergence = -(du_dx + dv_dy)

    # Circular mean for direction: a plain mean of 359 and 1 gives 180.
    radians = np.radians(direction)
    mean_direction = float(
        np.degrees(np.arctan2(np.mean(np.sin(radians)), np.mean(np.cos(radians))))
        % 360.0
    )
    circular_std = float(
        np.degrees(np.sqrt(-2 * np.log(
            np.hypot(np.mean(np.sin(radians)), np.mean(np.cos(radians))) + 1e-12
        )))
    )

    features = {
        "flow_magnitude_mean": float(np.mean(magnitude)),
        "flow_magnitude_std": float(np.std(magnitude)),
        "flow_magnitude_max": float(np.max(magnitude)),
        "flow_direction_mean": mean_direction,
        "flow_direction_std": min(circular_std, 360.0),
        "convergence_mean": float(np.mean(convergence)),
        "convergence_max": float(np.max(convergence)),
        "convergence_min": float(np.min(convergence)),
        "convergence_std": float(np.std(convergence)),
        "convergence_in_cold_cloud": 0.0,
    }

    if bt_field is not None:
        cold = convective_mask(ensure_kelvin(bt_field), config.BT_CONVECTIVE_K)
        if cold.any():
            features["convergence_in_cold_cloud"] = float(
                np.mean(convergence[cold])
            )

    return features


# --------------------------------------------------------------------------
# Nowcasting
# --------------------------------------------------------------------------

def nowcast_sequence(frames: Sequence[np.ndarray],
                     lead_times_hours: Sequence[int] = config.LEAD_TIMES_HOURS,
                     interval_minutes: float = config.SATELLITE_INTERVAL_MIN,
                     ) -> Tuple[List[np.ndarray], np.ndarray]:
    """
    Advect the latest frame forward to each lead time.

    Args:
        frames: chronological IR fields, at least two.
        lead_times_hours: forecast lead times.
        interval_minutes: spacing between input frames. Flow is measured PER
            FRAME INTERVAL, so converting a lead time in hours to a number of
            advection steps requires this. The original code advected by
            ``lead_time_steps=1..6`` and captioned the result "6 hours ahead",
            which silently assumed hourly frames - wrong for 30-minute INSAT
            imagery, by a factor of two.

    Returns:
        (nowcast frames, the flow field used)
    """
    if len(frames) < 2:
        raise ValueError("Need at least two frames to estimate motion.")

    flow = compute_optical_flow(frames[-2], frames[-1])
    steps_per_hour = 60.0 / interval_minutes

    nowcasts = [
        advect(frames[-1], flow, steps=lead * steps_per_hour)
        for lead in lead_times_hours
    ]
    return nowcasts, flow


def persistence_baseline(frames: Sequence[np.ndarray],
                         lead_times_hours: Sequence[int] = config.LEAD_TIMES_HOURS,
                         ) -> List[np.ndarray]:
    """
    Eulerian persistence: assume nothing moves or changes.

    This is the baseline every nowcast must beat. Reporting a CSI without
    comparing against it says nothing about whether the model adds value.
    """
    return [np.array(frames[-1], copy=True) for _ in lead_times_hours]


def storm_cell_tracks(frames: Sequence[np.ndarray],
                      interval_minutes: float = config.SATELLITE_INTERVAL_MIN,
                      ) -> List[Dict]:
    """
    Track convective cells across the frame sequence.

    Cells are identified as connected cold regions, then matched between
    consecutive frames by nearest centroid. Gives per-cell speed, bearing and
    whether the cell is growing or decaying - the information a forecaster
    actually wants from a nowcast.
    """
    tracks: List[Dict] = []
    previous: List[Dict] = []

    for index, frame in enumerate(frames):
        field = ensure_kelvin(frame)
        binary = convective_mask(field, config.BT_CONVECTIVE_K).astype(np.uint8)

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            binary, connectivity=8
        )

        current: List[Dict] = []
        for label in range(1, count):
            area = int(stats[label, cv2.CC_STAT_AREA])
            if area < 40:            # ignore speckle
                continue
            cell_mask = labels == label
            current.append({
                "centroid": (float(centroids[label][0]), float(centroids[label][1])),
                "area": area,
                "min_bt": float(np.min(field[cell_mask])),
                "frame": index,
            })

        # Match to the previous frame by nearest centroid.
        for cell in current:
            best, best_distance = None, 1e9
            for candidate in previous:
                distance = float(np.hypot(
                    cell["centroid"][0] - candidate["centroid"][0],
                    cell["centroid"][1] - candidate["centroid"][1],
                ))
                if distance < best_distance:
                    best, best_distance = candidate, distance

            if best is not None and best_distance < 40:
                dx = cell["centroid"][0] - best["centroid"][0]
                dy = cell["centroid"][1] - best["centroid"][1]
                cell["speed_px_per_frame"] = float(np.hypot(dx, dy))
                cell["bearing_deg"] = float(np.degrees(np.arctan2(dx, -dy)) % 360)
                cell["area_change"] = cell["area"] - best["area"]
                cell["bt_change"] = cell["min_bt"] - best["min_bt"]
                cell["intensifying"] = bool(
                    cell["bt_change"] < -1.0 or cell["area_change"] > best["area"] * 0.15
                )

        tracks.extend(current)
        previous = current

    return tracks


# --------------------------------------------------------------------------
# Visualisation
# --------------------------------------------------------------------------

def visualise_flow(flow: np.ndarray,
                   background: Optional[np.ndarray] = None,
                   step: int = 16,
                   color: Tuple[int, int, int] = (0, 255, 120)) -> np.ndarray:
    """Draw flow arrows over a background frame."""
    if background is None:
        height, width = flow.shape[:2]
        canvas = np.zeros((height, width, 3), dtype=np.uint8)
    else:
        field = np.asarray(background)
        if field.ndim == 2:
            gray = field if field.dtype == np.uint8 else kelvin_to_counts(field)
            canvas = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        else:
            canvas = field.copy()

    height, width = flow.shape[:2]
    ys, xs = np.mgrid[step // 2:height:step, step // 2:width:step].reshape(2, -1)
    ys, xs = ys.astype(int), xs.astype(int)

    for x, y in zip(xs, ys):
        fx, fy = flow[y, x]
        if np.hypot(fx, fy) < 0.5:
            continue
        cv2.arrowedLine(
            canvas, (x, y), (int(x + fx * 3), int(y + fy * 3)),
            color, 1, tipLength=0.35,
        )

    return canvas
