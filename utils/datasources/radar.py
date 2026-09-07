"""
utils/datasources/radar.py
IMD Doppler Weather Radar ingestion - the "multiple radars" leg of PS 26072.

IMD publishes DWR products publicly as GIF images at

    https://mausam.imd.gov.in/Radar/{product}_{station}.gif

where product is one of:

    caz   Composite maximum reflectivity   <- the one that matters for storms
    ppz   PPI reflectivity (lowest tilt)
    ppv   PPI radial velocity              <- rotation, mesocyclone signature
    ppi   PPI base product
    sri   Surface rainfall intensity
    pac   Precipitation accumulation
    vp2   Volume velocity processing / VAD wind profile

These are rendered products, not Level-II volumes: the reflectivity is encoded
in the colour palette rather than carried as physical dBZ. This module inverts
the palette to recover an approximate dBZ field, and is explicit that this is
an approximation. An operational deployment would ingest the Level-II volumes
that IMD provides to registered institutional users instead.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

import config
from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    cache_binary_path,
    haversine_km,
    http_get,
    last_error,
    nearest_radars,
    timed,
)

RADAR_BASE = config.IMD_RADAR_BASE

PRODUCTS = {
    "caz": "Composite maximum reflectivity",
    "ppz": "PPI reflectivity",
    "ppv": "PPI radial velocity",
    "sri": "Surface rainfall intensity",
    "pac": "Precipitation accumulation",
    "vp2": "VAD wind profile",
}

# Station code -> URL slug used by mausam.imd.gov.in.
STATION_SLUGS: Dict[str, str] = {
    "DEL": "delhi",
    "MUM": "mumbai",
    "CHN": "chennai",
    "KOL": "kolkata",
    "NAG": "nagpur",
    "HYD": "hyderabad",
    "JAI": "jaipur",
    "LKO": "lucknow",
    "PAT": "patna",
    "BHO": "bhopal",
    "AHM": "ahmedabad",
    "GOA": "goa",
    "VIS": "vishakhapatnam",
    "MCH": "machilipatnam",
    "SHR": "sriharikota",
    "KAR": "karaikal",
    "KOC": "kochi",
    "THI": "thiruvananthapuram",
    "BNG": "bengaluru",
    "MOH": "mohanbari",
    "AGT": "agartala",
    "PDP": "paradip",
    "GOP": "gopalpur",
    "BHJ": "bhuj",
    "PTL": "patiala",
    "KUF": "kufri",
    "MUK": "mukteshwar",
    "JOT": "jot",
    "MUR": "murari",
    "SRN": "srinagar",
    "JMU": "jammu",
    "DDN": "dehradun",
    "GHY": "guwahati",
    "VER": "veravali",
    "LAN": "lansdowne",
    "CHE": "sohra",
}


# --------------------------------------------------------------------------
# dBZ palette inversion
# --------------------------------------------------------------------------
# IMD MAX_Z products PRINT THEIR OWN COLOUR SCALE inside the image: a column
# of swatches on the right, labelled 20.0 dBZ at the bottom through >60.0 dBZ
# at the top. Reading that legend at runtime is far more robust than
# hardcoding a palette, because it adapts automatically when a station uses a
# different scale or IMD restyles the product.
#
# The fallback palette below is only used when the legend cannot be located.
# It matches the observed IMD scale: violet -> blue -> cyan -> white -> yellow
# -> orange -> red.

FALLBACK_PALETTE: List[Tuple[Tuple[int, int, int], float]] = [
    ((58, 0, 160), 21.3), ((0, 25, 176), 26.7), ((0, 58, 200), 29.3),
    ((0, 71, 255), 32.0), ((0, 121, 255), 34.7), ((26, 163, 255), 37.3),
    ((83, 209, 255), 40.0), ((135, 241, 255), 42.7), ((255, 255, 255), 45.3),
    ((252, 252, 122), 48.0), ((255, 230, 0), 50.7), ((255, 189, 0), 53.3),
    ((255, 115, 0), 56.0), ((255, 63, 0), 58.7), ((200, 0, 0), 61.0),
]

# The printed scale runs from 20 dBZ to just over 60 dBZ.
LEGEND_MIN_DBZ = 20.0
LEGEND_MAX_DBZ = 61.0


def extract_legend_palette(image: np.ndarray
                           ) -> Optional[List[Tuple[Tuple[int, int, int], float]]]:
    """
    Read the reflectivity colour scale printed inside the product image.

    Scans the right-hand portion of the frame for the column containing the
    most distinct, evenly-sized vertical colour bands - that is the legend -
    and assigns dBZ values across the printed 20 to 60+ range.

    Returns None when no legend is found, so the caller can fall back.
    """
    height, width = image.shape[:2]
    best: Optional[Tuple[int, List]] = None
    best_score = 0

    def is_chromatic(pixel: Tuple[int, int, int]) -> bool:
        """True for a saturated colour - not white, black or grey text."""
        hi, lo = max(pixel), min(pixel)
        return hi > 60 and (hi - lo) > 60

    # The legend sits in the right ~20% of the frame.
    for x in range(int(width * 0.80), width):
        runs: List[Tuple[int, int, Tuple[int, int, int]]] = []
        previous, start = None, None

        for y in range(int(height * 0.4), int(height * 0.95)):
            pixel = tuple(int(v) for v in image[y, x, :3])
            if pixel != previous:
                if previous is not None and start is not None:
                    runs.append((start, y - start, previous))
                previous, start = pixel, y
        if previous is not None and start is not None:
            runs.append((start, int(height * 0.95) - start, previous))

        # Legend swatches are uniform blocks of ~10-24 px.
        swatches = [r for r in runs if 10 <= r[1] <= 24]
        if len(swatches) < 10:
            continue

        # Score on DISTINCT CHROMATIC colours. A column of white text produces
        # many equal-sized runs but only one colour, and must not win.
        distinct = {s[2] for s in swatches}
        chromatic = {c for c in distinct if is_chromatic(c)}
        score = len(chromatic)

        if score >= 8 and score > best_score:
            best, best_score = (x, swatches), score

    if best is None:
        return None

    _, swatches = best
    swatches.sort(key=lambda r: r[0])          # top to bottom

    # Keep only chromatic swatches plus the single white band that genuinely
    # belongs to the IMD scale (around 45 dBZ), dropping white padding at the
    # extreme ends.
    while swatches and not is_chromatic(swatches[0][2]):
        swatches.pop(0)
    while swatches and not is_chromatic(swatches[-1][2]):
        swatches.pop()

    if len(swatches) < 8:
        return None

    # Top of the legend is the highest reflectivity.
    values = np.linspace(LEGEND_MAX_DBZ, LEGEND_MIN_DBZ, len(swatches))
    return [(s[2], float(v)) for s, v in zip(swatches, values)]


def detect_scan_area(image: np.ndarray) -> np.ndarray:
    """
    Mask the circular PPI scan area, excluding panels, legend and title bar.

    The IMD MAX_Z layout puts vertical cross-section panels above and to the
    right of the main disc, plus a legend box - all drawn in the same palette
    colours as the echoes. Decoding those as reflectivity is what produced a
    spurious 60+ dBZ core on every single fetch.

    The disc is located from the green terrain basemap, which appears only
    inside the scan circle; the cross-section panels use a tan background.
    """
    height, width = image.shape[:2]
    red = image[:, :, 0].astype(np.int16)
    green = image[:, :, 1].astype(np.int16)
    blue = image[:, :, 2].astype(np.int16)

    # Green terrain basemap: green channel clearly dominant.
    basemap = (green - red > 20) & (green - blue > 20) & (green > 80)

    ys, xs = np.where(basemap)
    if ys.size < 500:
        # No recognisable basemap: fall back to the inscribed circle.
        yy, xx = np.ogrid[:height, :width]
        cy, cx = height / 2.0, width / 2.0
        radius = min(height, width) / 2.0 * 0.92
        return ((yy - cy) ** 2 + (xx - cx) ** 2) <= radius ** 2

    # Robust centre and radius from the basemap point cloud.
    cx, cy = float(np.median(xs)), float(np.median(ys))
    distances = np.hypot(xs - cx, ys - cy)
    radius = float(np.percentile(distances, 99))

    yy, xx = np.ogrid[:height, :width]
    disc = ((yy - cy) ** 2 + (xx - cx) ** 2) <= radius ** 2

    # Intersect with the basemap's own bounding box. The fitted circle can
    # overhang into the cross-section panels above and to the right of the
    # disc, which carry echo-coloured pixels of their own; the box clips them.
    top, bottom = np.percentile(ys, [0.5, 99.5])
    left, right = np.percentile(xs, [0.5, 99.5])
    box = np.zeros((height, width), dtype=bool)
    box[int(top):int(bottom) + 1, int(left):int(right) + 1] = True

    return disc & box


def palette_to_dbz(rgb_image: np.ndarray,
                   mask_furniture: bool = True,
                   palette: Optional[List] = None) -> np.ndarray:
    """
    Recover an approximate dBZ field by nearest-colour matching.

    Pixels that match no palette colour closely - terrain basemap, coastlines,
    range rings, station labels - are returned as NaN rather than 0 dBZ, so
    "no echo" and "not radar data" stay distinguishable.

    Args:
        mask_furniture: restrict decoding to the detected PPI scan circle.
        palette: explicit palette; by default the one printed in the image is
            used, falling back to FALLBACK_PALETTE.
    """
    image = np.asarray(rgb_image, dtype=np.int16)
    if image.ndim != 3 or image.shape[2] < 3:
        raise ValueError("expected an RGB image")
    image = image[:, :, :3]

    if palette is None:
        palette = extract_legend_palette(image) or FALLBACK_PALETTE

    # Drop achromatic entries from the MATCHING palette. The IMD scale
    # includes a white band near 43 dBZ, but white is also the page
    # background, the legend box, every text label and the panel borders.
    # Keeping it made half the frame decode as a 43 dBZ echo. Chromatic
    # swatches are unambiguous, and a true white echo pixel simply falls to
    # its neighbouring cyan or yellow band - a sub-3 dBZ error, against a
    # 50-percentage-point error in coverage the other way.
    def chromatic(colour) -> bool:
        hi, lo = max(colour), min(colour)
        return hi > 60 and (hi - lo) > 60

    usable = [(c, v) for c, v in palette if chromatic(c)]
    if len(usable) < 5:
        usable = [(c, v) for c, v in FALLBACK_PALETTE if chromatic(c)]

    colours = np.array([c for c, _ in usable], dtype=np.int32)
    values = np.array([v for _, v in usable], dtype=np.float32)

    # int32 is required. A squared channel difference reaches 255^2 = 65025 and
    # the three-channel sum reaches 195075, both far beyond the int16 maximum
    # of 32767. Computing this in int16 wraps around, so genuinely distant
    # colours - the green terrain basemap in particular - scored as near
    # matches and half the frame decoded as a 40 dBZ echo.
    flat = image.reshape(-1, 3).astype(np.int32)
    distances = np.sum((flat[:, None, :] - colours[None, :, :]) ** 2, axis=2)
    nearest = np.argmin(distances, axis=1)
    best_distance = distances[np.arange(flat.shape[0]), nearest]

    dbz = values[nearest].astype(np.float32)
    # Tight tolerance: echoes are drawn in flat palette colours, so a genuine
    # echo pixel matches almost exactly. Anything further away is basemap.
    dbz[best_distance > 12 ** 2] = np.nan

    # The query pixel must itself be saturated. Terrain green and tan sit
    # close to some palette entries in raw RGB distance but are visibly
    # desaturated; this rejects them.
    hi = flat.max(axis=1)
    lo = flat.min(axis=1)
    dbz[(hi <= 60) | ((hi - lo) <= 60)] = np.nan

    dbz = dbz.reshape(image.shape[0], image.shape[1])

    if mask_furniture:
        dbz[~detect_scan_area(image)] = np.nan

    return dbz


def reflectivity_features(dbz: np.ndarray) -> Dict[str, float]:
    """
    Storm-relevant statistics from a reflectivity field.

    The thresholds are the operational ones: 35 dBZ marks a convective core,
    50 dBZ indicates hail-bearing or intense convection, and echo coverage
    tracks how much of the domain is active.
    """
    valid = dbz[np.isfinite(dbz)]
    if valid.size == 0:
        return {
            "max_reflectivity_dbz": 0.0,
            "mean_reflectivity_dbz": 0.0,
            "echo_coverage_fraction": 0.0,
            "convective_fraction": 0.0,
            "intense_core_fraction": 0.0,
            "reflectivity_std": 0.0,
        }

    total = float(dbz.size)

    # Robust maximum. A raw np.max is set by a single stray pixel - a residual
    # annotation artefact or an isolated decoding error - and would report a
    # 75 dBZ core on an otherwise quiet scan. The 99.9th percentile needs a
    # genuine cluster of high-reflectivity pixels before it moves.
    robust_max = float(np.percentile(valid, 99.9)) if valid.size > 100 else float(np.max(valid))

    return {
        "max_reflectivity_dbz": robust_max,
        "mean_reflectivity_dbz": float(np.mean(valid)),
        "echo_coverage_fraction": float(valid.size / total),
        "convective_fraction": float(np.sum(valid >= 35.0) / total),
        "intense_core_fraction": float(np.sum(valid >= 50.0) / total),
        "reflectivity_std": float(np.std(valid)),
    }


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

@timed
def fetch_radar(station_code: str, product: str = "caz") -> SourceResult:
    """Fetch one DWR product image and decode it to approximate dBZ."""
    slug = STATION_SLUGS.get(station_code.upper())
    if slug is None:
        return SourceResult(
            source=f"IMD DWR {station_code}",
            status=SourceStatus.UNAVAILABLE,
            message=f"No URL slug known for station {station_code}.",
            citation="India Meteorological Department",
        )

    url = f"{RADAR_BASE}/{product}_{slug}.gif"
    response = http_get(url, retries=1, timeout=12)

    if response is None or "image" not in response.headers.get("content-type", ""):
        return SourceResult(
            source=f"IMD DWR {station_code} ({product})",
            status=SourceStatus.UNAVAILABLE,
            message=(
                f"{station_code} is not currently publishing {product}. "
                f"({last_error(url)})"
            ),
            citation="India Meteorological Department, mausam.imd.gov.in",
            metadata={"url": url},
        )

    try:
        from PIL import Image

        image = Image.open(io.BytesIO(response.content)).convert("RGB")
        array = np.array(image)
        dbz = palette_to_dbz(array)
        features = reflectivity_features(dbz)

        # Keep the raw frame so the UI can display it.
        path = cache_binary_path(f"radar:{station_code}:{product}", ".gif")
        path.write_bytes(response.content)

        station = next(
            (s for s in config.DWR_NETWORK if s.code == station_code.upper()), None
        )

        return SourceResult(
            source=f"IMD DWR {station_code} ({PRODUCTS.get(product, product)})",
            status=SourceStatus.LIVE,
            data={
                "dbz": dbz,
                "rgb": array,
                "features": features,
                "image_path": str(path),
                "station": {
                    "code": station_code.upper(),
                    "city": station.city if station else station_code,
                    "lat": station.lat if station else None,
                    "lon": station.lon if station else None,
                    "band": station.band if station else "?",
                },
            },
            valid_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            message=(
                f"Max {features['max_reflectivity_dbz']:.0f} dBZ, "
                f"convective coverage {features['convective_fraction']:.1%}"
            ),
            citation="India Meteorological Department, mausam.imd.gov.in",
            metadata={"url": url, "product": product,
                      "note": "dBZ approximated by palette inversion"},
        )

    except Exception as exc:
        return SourceResult(
            source=f"IMD DWR {station_code} ({product})",
            status=SourceStatus.UNAVAILABLE,
            message=f"Could not decode radar image: {exc}",
            citation="India Meteorological Department",
        )


@timed
def fetch_radar_mosaic(lat: float,
                       lon: float,
                       max_stations: int = 3,
                       product: str = "caz") -> SourceResult:
    """
    Multi-radar composite for a location - literally "multiple radars".

    Queries the nearest DWR sites, keeps whichever respond, and merges their
    features with inverse-distance weighting so a nearby radar dominates.
    Reports exactly which stations contributed, because a composite built from
    one radar is a very different claim from one built from four.
    """
    candidates = nearest_radars(lat, lon, n=max_stations + 3)

    contributing: List[Dict] = []
    attempted: List[Dict] = []

    # Fetched CONCURRENTLY. Sequentially, with two retries and a 20 s timeout
    # each, six unreachable stations took over three minutes to report that
    # none of them answered - which stalls the whole nowcast whenever IMD is
    # having a bad day, and IMD has bad days. The sites are independent, so
    # there is no reason to wait for one before starting the next.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        futures = [
            (candidate, pool.submit(fetch_radar, candidate["code"], product))
            for candidate in candidates
        ]
        results = []
        for candidate, future in futures:
            try:
                results.append((candidate, future.result(timeout=45)))
            except Exception as exc:
                results.append((candidate, SourceResult(
                    source=f"IMD DWR {candidate['code']}",
                    status=SourceStatus.UNAVAILABLE,
                    message=f"probe failed: {exc}",
                )))

    # Keep the nearest live sites, in distance order.
    for candidate, result in results:
        attempted.append({
            "code": candidate["code"],
            "city": candidate["city"],
            "distance_km": candidate["distance_km"],
            "status": result.status.value,
            "message": result.message,
        })
        if (result.status == SourceStatus.LIVE
                and len(contributing) < max_stations):
            contributing.append({
                "code": candidate["code"],
                "city": candidate["city"],
                "distance_km": candidate["distance_km"],
                "features": result.data["features"],
                "image_path": result.data["image_path"],
                "lat": candidate["lat"],
                "lon": candidate["lon"],
            })

    if not contributing:
        return SourceResult(
            source="IMD DWR multi-radar composite",
            status=SourceStatus.UNAVAILABLE,
            message=(
                f"None of the {len(attempted)} nearest radar sites are "
                "currently publishing public products."
            ),
            citation="India Meteorological Department",
            metadata={"attempted": attempted},
        )

    # Inverse-distance weighting, floored so a co-located radar cannot dominate
    # to the point of numerical blow-up.
    weights = np.array([1.0 / max(c["distance_km"], 25.0) for c in contributing])
    weights = weights / weights.sum()

    merged: Dict[str, float] = {}
    for key in contributing[0]["features"]:
        values = np.array([c["features"][key] for c in contributing])
        if key == "max_reflectivity_dbz":
            merged[key] = float(np.max(values))   # a max must stay a max
        else:
            merged[key] = float(np.sum(values * weights))

    return SourceResult(
        source=f"IMD DWR composite ({len(contributing)} radar"
               f"{'s' if len(contributing) > 1 else ''})",
        status=SourceStatus.LIVE,
        data={
            "features": merged,
            "stations": contributing,
            "attempted": attempted,
        },
        valid_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        message=(
            f"{len(contributing)} of {len(attempted)} nearest radars live: "
            + ", ".join(c["code"] for c in contributing)
        ),
        citation="India Meteorological Department, mausam.imd.gov.in",
        metadata={"product": product},
    )


def network_status(product: str = "caz",
                   limit: Optional[int] = None,
                   timeout: float = 4.0,
                   deadline: float = 12.0) -> List[Dict]:
    """
    Probe the DWR network and report which sites are publishing.

    Used by the 3D globe to colour each radar site by live status, and by the
    diagnostics panel to show honestly how much of the network is reachable.

    PERFORMANCE MATTERS HERE. This ran sequentially with retries and an 8 s
    timeout, so when IMD was unreachable it took 97 seconds to report that 0
    of 12 sites were live. Streamlit executes every tab body on every rerun,
    so that blocked the entire application on each interaction and looked
    exactly like a hung deployment.

    It is now issued concurrently, with a single attempt, a short per-request
    timeout and a hard overall deadline. A liveness probe should fail fast:
    an unreachable site is itself the answer, and waiting longer does not make
    it a better one. Any site not resolved within the deadline is reported as
    not live rather than holding up the render.
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    stations = list(config.DWR_NETWORK)[:limit]

    def probe(station) -> bool:
        slug = STATION_SLUGS.get(station.code)
        if not slug:
            return False
        response = http_get(
            f"{RADAR_BASE}/{product}_{slug}.gif",
            retries=1, timeout=timeout,
        )
        return (
            response is not None
            and "image" in response.headers.get("content-type", "")
        )

    live_map: Dict[str, bool] = {}
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=min(12, max(1, len(stations)))) as pool:
        futures = {pool.submit(probe, s): s.code for s in stations}
        for future in as_completed(futures, timeout=None):
            code = futures[future]
            try:
                live_map[code] = bool(future.result(timeout=0.1))
            except Exception:
                live_map[code] = False
            if time.perf_counter() - started > deadline:
                break  # report what resolved; the rest default to not live

    return [
        {
            "code": station.code,
            "city": station.city,
            "lat": station.lat,
            "lon": station.lon,
            "band": station.band,
            "range_km": station.range_km,
            "live": live_map.get(station.code, False),
        }
        for station in stations
    ]
