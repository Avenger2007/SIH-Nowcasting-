"""
utils/datasources/boundaries.py
Official Indian administrative boundaries from ISRO Bhuvan (NRSC).

WHY THIS SOURCE AND NO OTHER
----------------------------
India's official external boundary - particularly in Jammu & Kashmir and
Ladakh - differs from the de-facto lines shown by international datasets.
Natural Earth, OpenStreetMap, GADM and most Western basemaps depict the Line
of Control rather than the boundary the Government of India recognises.
Rendering one of those in a submission to the Ministry of Earth Sciences would
be, at best, a serious unforced error.

Every boundary drawn by this project therefore comes from **ISRO Bhuvan**, the
national geoportal operated by the National Remote Sensing Centre under the
Department of Space, Government of India. Bhuvan's ``basemap`` layers carry
the Survey of India depiction, which is the authoritative one.

    Service : https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms  (OGC WMS 1.1.1)
    Layers  : basemap:STATE_BDY_UPD    state boundaries, updated
              basemap:india_state_ql   states, filled
              basemap:INDIA_DIST       district boundaries
              basemap:INDIA_STATE      states with labels

Verified current as of this build: Ladakh appears as a Union Territory
distinct from Jammu & Kashmir, reflecting the 2019 reorganisation, and the
external boundary follows the official Indian depiction.

This module never falls back to a non-authoritative source. If Bhuvan cannot
be reached it reports UNAVAILABLE and the globe simply renders without
boundaries, because drawing the wrong border is worse than drawing none.
"""

from __future__ import annotations

import base64
import io
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import config
from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    cache_binary_path,
    http_get,
    last_error,
    timed,
)

BHUVAN_WMS = "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms"
BHUVAN_WMS_FALLBACKS = (
    "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms",
    "https://bhuvan-vec2.nrsc.gov.in/bhuvan/wms",
    "https://bhuvan-vec3.nrsc.gov.in/bhuvan/wms",
)

ATTRIBUTION = (
    "Administrative boundaries: ISRO Bhuvan / National Remote Sensing Centre, "
    "Department of Space, Government of India. Survey of India depiction."
)

LAYERS: Dict[str, Dict[str, str]] = {
    "state_lines": {
        "layer": "basemap:STATE_BDY_UPD",
        "label": "State boundaries (updated)",
        "note": "Line work only. Ideal as an overlay on satellite or radar imagery.",
    },
    "state_filled": {
        "layer": "basemap:india_state_ql",
        "label": "States, filled",
        "note": "Filled polygons. Used as the globe texture.",
    },
    "state_labelled": {
        "layer": "basemap:INDIA_STATE",
        "label": "States with labels",
        "note": "Includes state name labels.",
    },
    "districts": {
        "layer": "basemap:INDIA_DIST",
        "label": "District boundaries",
        "note": "Finer administrative detail.",
    },
}

# The analysis domain, matching config.INDIA_BBOX.
DEFAULT_BBOX: Tuple[float, float, float, float] = config.INDIA_BBOX

# Boundaries change on the order of years, so cache aggressively.
BOUNDARY_CACHE_TTL = 30 * 24 * 3600


@timed
def fetch_boundary_layer(kind: str = "state_lines",
                         bbox: Optional[Tuple[float, float, float, float]] = None,
                         width: int = 1024,
                         height: int = 1024,
                         transparent: bool = True) -> SourceResult:
    """
    Fetch one boundary layer from Bhuvan as a PNG.

    Args:
        kind: key from LAYERS.
        bbox: (lon_min, lat_min, lon_max, lat_max) in EPSG:4326.
        width, height: output raster size.
        transparent: transparent background, for overlaying.

    Returns a SourceResult whose ``data`` carries the PNG bytes, a base64
    data URI ready for the browser, and the bbox the image covers.
    """
    spec = LAYERS.get(kind)
    if spec is None:
        return SourceResult(
            source="ISRO Bhuvan boundaries",
            status=SourceStatus.UNAVAILABLE,
            message=f"Unknown boundary layer '{kind}'. "
                    f"Known: {', '.join(LAYERS)}",
            citation=ATTRIBUTION,
        )

    bbox = bbox or DEFAULT_BBOX
    lon_min, lat_min, lon_max, lat_max = bbox

    cache_key = f"bhuvan:{kind}:{bbox}:{width}x{height}:{transparent}"
    cache_path = cache_binary_path(cache_key, ".png")

    # Serve from cache when fresh - boundaries are effectively static.
    if cache_path.exists():
        age = (datetime.now(timezone.utc).timestamp()
               - cache_path.stat().st_mtime)
        if age < BOUNDARY_CACHE_TTL:
            payload = cache_path.read_bytes()
            return _result(kind, spec, payload, bbox, SourceStatus.CACHED,
                           f"Served from cache, {age / 86400:.1f} days old.")

    params = {
        "service": "WMS",
        "version": "1.1.1",
        "request": "GetMap",
        "layers": spec["layer"],
        "styles": "",
        "bbox": f"{lon_min},{lat_min},{lon_max},{lat_max}",
        "srs": "EPSG:4326",
        "width": width,
        "height": height,
        "format": "image/png",
        "transparent": "true" if transparent else "false",
    }

    for endpoint in BHUVAN_WMS_FALLBACKS:
        response = http_get(endpoint, params=params, retries=1, timeout=90)
        if response is None:
            continue
        if "image" not in response.headers.get("content-type", ""):
            continue
        if len(response.content) < 800:
            continue

        payload = response.content
        try:
            cache_path.write_bytes(payload)
        except OSError:
            pass

        return _result(kind, spec, payload, bbox, SourceStatus.LIVE,
                       f"Fetched from {endpoint.split('//')[1].split('/')[0]}.")

    # Stale cache beats no boundary at all.
    if cache_path.exists():
        payload = cache_path.read_bytes()
        return _result(kind, spec, payload, bbox, SourceStatus.STALE,
                       "Bhuvan unreachable; serving the cached boundary.")

    return SourceResult(
        source=f"ISRO Bhuvan - {spec['label']}",
        status=SourceStatus.UNAVAILABLE,
        message=(
            "Could not reach ISRO Bhuvan. No boundary will be drawn: this "
            "project deliberately does NOT fall back to Natural Earth, OSM or "
            "GADM, because those depict the Line of Control rather than the "
            "official Indian boundary. "
            f"({last_error(BHUVAN_WMS)})"
        ),
        citation=ATTRIBUTION,
        metadata={"layer": spec["layer"], "endpoints_tried": len(BHUVAN_WMS_FALLBACKS)},
    )


def _result(kind: str, spec: Dict, payload: bytes,
            bbox: Tuple[float, float, float, float],
            status: SourceStatus, message: str) -> SourceResult:
    """Wrap PNG bytes into a SourceResult with a browser-ready data URI."""
    data_uri = "data:image/png;base64," + base64.b64encode(payload).decode("ascii")

    return SourceResult(
        source=f"ISRO Bhuvan - {spec['label']}",
        status=status,
        data={
            "png": payload,
            "data_uri": data_uri,
            "bbox": bbox,
            "layer": spec["layer"],
            "kind": kind,
        },
        valid_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        message=f"{message} {spec['note']}",
        citation=ATTRIBUTION,
        metadata={
            "layer": spec["layer"],
            "bytes": len(payload),
            "authority": "National Remote Sensing Centre, Department of Space, "
                         "Government of India",
            "depiction": "Survey of India (official Indian boundary)",
        },
    )


def overlay_on_raster(base_rgb, boundary_result: SourceResult,
                      opacity: float = 0.85):
    """
    Composite the boundary line work over an image raster.

    Used to draw state boundaries on top of INSAT imagery so a forecaster can
    see immediately which states a storm system covers.

    Args:
        base_rgb: HxWx3 uint8 array, or HxW greyscale.
        boundary_result: from :func:`fetch_boundary_layer`.
        opacity: line opacity.

    Returns the composited RGB array, or the input unchanged when no boundary
    is available.
    """
    import numpy as np
    from PIL import Image

    base = np.asarray(base_rgb)
    if base.ndim == 2:
        base = np.stack([base] * 3, axis=-1)
    base = base.astype(np.uint8)

    if not boundary_result.ok:
        return base

    height, width = base.shape[:2]
    overlay = Image.open(io.BytesIO(boundary_result.data["png"])).convert("RGBA")
    overlay = overlay.resize((width, height), Image.LANCZOS)
    layer = np.array(overlay)

    alpha = (layer[:, :, 3:4].astype(np.float32) / 255.0) * opacity

    # Bhuvan draws boundaries in near-black; recolour to a high-contrast
    # cyan so the lines stay legible over dark infrared cloud imagery.
    ink = np.zeros_like(layer[:, :, :3])
    ink[:, :] = (90, 220, 255)

    blended = base.astype(np.float32) * (1 - alpha) + ink.astype(np.float32) * alpha
    return np.clip(blended, 0, 255).astype(np.uint8)


def boundary_data_uri(kind: str = "state_filled") -> Optional[str]:
    """Convenience accessor returning just the data URI, or None."""
    result = fetch_boundary_layer(kind)
    return result.data["data_uri"] if result.ok else None
