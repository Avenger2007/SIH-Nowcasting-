"""
utils/geo.py
Geostationary projection - turning INSAT full-disk pixels into real coordinates.

The original code (and the first pass of this rebuild) cut the Indian region
out of the INSAT full disk using fixed pixel fractions. That is fine for a
thumbnail and useless for anything georeferenced: features could not be tied to
a location, and an administrative boundary drawn over the crop would be
misregistered by tens of kilometres.

This module implements the standard geostationary (GEOS) projection used by
INSAT, Meteosat and GOES, following the CGMS/LRIT formulation, so a full-disk
image can be resampled onto a proper latitude/longitude grid.

The result is that:
  * satellite features are extracted for an actual bounding box;
  * the ISRO Bhuvan boundary overlays line up with the coastline in the
    imagery, which is the visual check that the projection is right;
  * a per-city analysis box means what it says.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

# WGS-84 / CGMS constants.
EARTH_EQUATORIAL_RADIUS_KM = 6378.1370
EARTH_POLAR_RADIUS_KM = 6356.7523
SATELLITE_DISTANCE_KM = 42164.0          # Earth centre to geostationary orbit

# Ratio used in the geodetic-to-geocentric latitude conversion.
_RATIO = (EARTH_POLAR_RADIUS_KM ** 2) / (EARTH_EQUATORIAL_RADIUS_KM ** 2)
_ECCENTRICITY = 1.0 - _RATIO

# Angular radius of the Earth seen from geostationary orbit (~8.7 degrees).
MAX_VIEW_ANGLE = np.arcsin(EARTH_EQUATORIAL_RADIUS_KM / SATELLITE_DISTANCE_KM)


@dataclass
class DiskGeometry:
    """Where the Earth disk sits inside a full-disk image."""

    centre_x: float
    centre_y: float
    radius_px: float
    sub_satellite_lon: float = 82.0     # INSAT-3D; 3DR sits at 74 E

    @property
    def scale(self) -> float:
        """Pixels per radian of view angle."""
        return self.radius_px / MAX_VIEW_ANGLE


def detect_disk(image: np.ndarray,
                threshold: int = 12) -> Optional[DiskGeometry]:
    """
    Locate the Earth disk in a full-disk image.

    MOSDAC browse products are not bare disks: they carry a title bar, a
    greyscale colour wedge, and ISRO/MOSDAC logos across the top, all drawn in
    bright white. A naive threshold-and-bounding-box includes that furniture
    and drags the fitted centre upwards while inflating the radius - which
    then throws every derived coordinate out by hundreds of kilometres.

    The disk is therefore isolated as the largest CONNECTED COMPONENT, which
    the Earth always is by a wide margin, and a circle is fitted to that
    component alone.

    Returns None when no plausible disk is found.
    """
    array = np.asarray(image)
    if array.ndim == 3:
        array = array.mean(axis=2)
    array = array.astype(np.float32)

    mask = (array > threshold).astype(np.uint8)
    if mask.sum() < 1000:
        return None

    try:
        import cv2

        # Close small gaps so the disk is one component despite dark ocean.
        kernel = np.ones((7, 7), np.uint8)
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            closed, connectivity=8
        )
        if count < 2:
            return None

        # Largest component excluding the background label 0.
        areas = stats[1:, cv2.CC_STAT_AREA]
        best = int(np.argmax(areas)) + 1

        left = float(stats[best, cv2.CC_STAT_LEFT])
        top = float(stats[best, cv2.CC_STAT_TOP])
        width = float(stats[best, cv2.CC_STAT_WIDTH])
        height = float(stats[best, cv2.CC_STAT_HEIGHT])
        right, bottom = left + width, top + height

    except ImportError:  # pragma: no cover - OpenCV is a hard dependency
        ys, xs = np.where(mask)
        left, right = np.percentile(xs, [0.05, 99.95])
        top, bottom = np.percentile(ys, [0.05, 99.95])
        width, height = right - left, bottom - top

    if width < 50 or height < 50:
        return None

    # A full disk is circular; a wildly non-square bounding box is not one.
    aspect = width / height
    if not (0.85 < aspect < 1.18):
        return None

    coarse = DiskGeometry(
        centre_x=(left + right) / 2.0,
        centre_y=(top + bottom) / 2.0,
        radius_px=(width + height) / 4.0,
    )

    # A bounding box is only accurate to a pixel or two and is biased by any
    # ragged limb. Refining with a least-squares circle fit to the limb itself
    # removes a systematic scale error worth tens of kilometres on the ground.
    refined = _fit_limb_circle(mask, coarse)
    return refined or coarse


def _fit_limb_circle(mask: np.ndarray,
                     coarse: "DiskGeometry") -> Optional["DiskGeometry"]:
    """
    Least-squares circle fit to the Earth limb.

    Edge points are collected by scanning each row and column for the first
    and last lit pixel, then a Kasa algebraic fit solves for centre and radius
    in closed form. Points far from the coarse circle are rejected first, so
    stray annotation cannot drag the fit.
    """
    height, width = mask.shape[:2]
    points = []

    step = max(1, height // 400)
    for y in range(0, height, step):
        lit = np.where(mask[y] > 0)[0]
        if lit.size > 10:
            points.append((lit[0], y))
            points.append((lit[-1], y))

    step = max(1, width // 400)
    for x in range(0, width, step):
        lit = np.where(mask[:, x] > 0)[0]
        if lit.size > 10:
            points.append((x, lit[0]))
            points.append((x, lit[-1]))

    if len(points) < 50:
        return None

    pts = np.asarray(points, dtype=np.float64)
    dist = np.hypot(pts[:, 0] - coarse.centre_x, pts[:, 1] - coarse.centre_y)
    # Keep points close to the coarse limb; drop anything clearly not on it.
    keep = np.abs(dist - coarse.radius_px) < max(6.0, coarse.radius_px * 0.02)
    pts = pts[keep]
    if pts.shape[0] < 50:
        return None

    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones(x.shape[0])])
    b = x ** 2 + y ** 2
    try:
        solution, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None

    cx = solution[0] / 2.0
    cy = solution[1] / 2.0
    radius = np.sqrt(solution[2] + cx ** 2 + cy ** 2)

    if not np.isfinite(radius) or radius <= 0:
        return None
    # Refusing a wild correction guards against a pathological fit.
    if abs(radius - coarse.radius_px) > coarse.radius_px * 0.15:
        return None

    return DiskGeometry(centre_x=float(cx), centre_y=float(cy),
                        radius_px=float(radius))


def lonlat_to_pixel(lon: np.ndarray,
                    lat: np.ndarray,
                    geometry: DiskGeometry
                    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Forward GEOS projection: geographic coordinates to image pixels.

    Args:
        lon, lat: arrays of degrees.
        geometry: disk geometry for the image.

    Returns:
        (column, row, visible) where ``visible`` is False for points over the
        horizon from the satellite - those must not be sampled, or the far
        side of the Earth gets smeared around the limb.
    """
    lon_rad = np.radians(np.asarray(lon, dtype=np.float64))
    lat_rad = np.radians(np.asarray(lat, dtype=np.float64))
    lon0 = np.radians(geometry.sub_satellite_lon)

    # Geodetic latitude to geocentric latitude.
    geocentric_lat = np.arctan(_RATIO * np.tan(lat_rad))

    # Distance from Earth centre to the surface point.
    r_local = EARTH_POLAR_RADIUS_KM / np.sqrt(
        1.0 - _ECCENTRICITY * np.cos(geocentric_lat) ** 2
    )

    delta_lon = lon_rad - lon0

    # Vector from satellite to the surface point, in the satellite frame.
    r1 = SATELLITE_DISTANCE_KM - (
        r_local * np.cos(geocentric_lat) * np.cos(delta_lon)
    )
    r2 = -r_local * np.cos(geocentric_lat) * np.sin(delta_lon)
    r3 = r_local * np.sin(geocentric_lat)
    rn = np.sqrt(r1 ** 2 + r2 ** 2 + r3 ** 2)

    # Visibility: the point must be on the near side of the Earth.
    visible = (
        SATELLITE_DISTANCE_KM * (SATELLITE_DISTANCE_KM - r1)
        > (r2 ** 2 + r3 ** 2 * (EARTH_EQUATORIAL_RADIUS_KM ** 2)
           / (EARTH_POLAR_RADIUS_KM ** 2))
    )

    # Scan angles.
    #
    # Sign convention matters and is easy to get wrong. r3 is POSITIVE in the
    # northern hemisphere, so taking y_angle = arcsin(-r3/rn) - as the raw
    # CGMS listing does, for a scan that starts at the south - and then
    # subtracting it from centre_y places north BELOW the centre. The image is
    # stored north-up, so northern latitudes must map to SMALLER row indices.
    x_angle = np.arctan(-r2 / r1)
    y_angle = np.arcsin(np.clip(r3 / rn, -1.0, 1.0))

    column = geometry.centre_x + x_angle * geometry.scale
    row = geometry.centre_y - y_angle * geometry.scale

    return column, row, visible


def reproject_to_latlon(image: np.ndarray,
                        bbox: Tuple[float, float, float, float],
                        size: int = 256,
                        geometry: Optional[DiskGeometry] = None,
                        sub_satellite_lon: float = 82.0,
                        ) -> Tuple[Optional[np.ndarray], Optional[DiskGeometry]]:
    """
    Resample a full-disk image onto a regular latitude/longitude grid.

    Args:
        image: full-disk raster (2-D, or 3-D which is averaged to grey).
        bbox: (lon_min, lat_min, lon_max, lat_max) of the output.
        size: output raster is size x size.
        geometry: disk geometry; detected automatically when omitted.

    Returns:
        (resampled image, geometry used), or (None, None) if the disk could
        not be located.

    Nearest-neighbour sampling is used deliberately: the source is already an
    8-bit rendered product, and interpolating across the sharp edge of a
    convective anvil would invent cloud-top temperatures that were never
    observed.
    """
    array = np.asarray(image)
    if array.ndim == 3:
        array = array.mean(axis=2)

    if geometry is None:
        geometry = detect_disk(array)
        if geometry is None:
            return None, None
    geometry.sub_satellite_lon = sub_satellite_lon

    lon_min, lat_min, lon_max, lat_max = bbox

    # Output grid: north at the top, west on the left.
    lons = np.linspace(lon_min, lon_max, size)
    lats = np.linspace(lat_max, lat_min, size)
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    columns, rows, visible = lonlat_to_pixel(lon_grid, lat_grid, geometry)

    height, width = array.shape[:2]
    cols = np.rint(columns).astype(int)
    rws = np.rint(rows).astype(int)

    inside = (
        visible
        & (cols >= 0) & (cols < width)
        & (rws >= 0) & (rws < height)
    )

    output = np.zeros((size, size), dtype=array.dtype)
    output[inside] = array[rws[inside], cols[inside]]

    return output, geometry


def pixel_to_lonlat(column: float, row: float,
                    geometry: DiskGeometry) -> Optional[Tuple[float, float]]:
    """
    Inverse projection: image pixel to geographic coordinates.

    Returns None for pixels that fall off the Earth disk. Used to answer
    "what is under this pixel", and to verify the forward projection.
    """
    x_angle = (column - geometry.centre_x) / geometry.scale
    y_angle = -(row - geometry.centre_y) / geometry.scale

    cos_x, sin_x = np.cos(x_angle), np.sin(x_angle)
    cos_y, sin_y = np.cos(y_angle), np.sin(y_angle)

    a = SATELLITE_DISTANCE_KM * cos_x * cos_y
    b = (cos_y ** 2 + (1.0 / _RATIO) * sin_y ** 2)
    discriminant = (
        a ** 2
        - b * (SATELLITE_DISTANCE_KM ** 2 - EARTH_EQUATORIAL_RADIUS_KM ** 2)
    )
    if discriminant < 0:
        return None                      # ray misses the Earth

    distance = (a - np.sqrt(discriminant)) / b

    s1 = SATELLITE_DISTANCE_KM - distance * cos_x * cos_y
    s2 = distance * sin_x * cos_y
    s3 = distance * sin_y          # matches the forward sign convention above
    sxy = np.sqrt(s1 ** 2 + s2 ** 2)

    lon = np.degrees(np.arctan(s2 / s1)) + geometry.sub_satellite_lon
    lat = np.degrees(np.arctan((1.0 / _RATIO) * s3 / sxy))

    return float(lon), float(lat)


def describe(geometry: DiskGeometry) -> str:
    """Human-readable summary for the diagnostics panel."""
    return (
        f"Earth disk centred at ({geometry.centre_x:.0f}, "
        f"{geometry.centre_y:.0f}) px, radius {geometry.radius_px:.0f} px, "
        f"sub-satellite point 0 N {geometry.sub_satellite_lon:.0f} E. "
        f"Scale {geometry.scale:.0f} px/rad."
    )
