"""
utils/datasources/worldmap.py
The base Earth texture for the landing-page globe.

The globe used to be a plain blue sphere with one patch of India on it, which
told a visitor nothing about where India sits. This module supplies the rest
of the world: every coastline, every country in a colour distinct from its
neighbours, and one blue for every ocean, sea and inland water body.

WHERE THE PIXELS COME FROM
--------------------------
``data/world/earth_texture.png`` is a 4096x2048 equirectangular raster built
offline by ``tools/build_world_atlas.py`` from Natural Earth 1:110m, and
committed to the repository. Nothing is fetched at runtime, so the landing
page renders identically offline, on a fresh container, and on a judge's
laptop behind a firewall.

INDIA IS NOT IN THIS TEXTURE, AND THAT IS DELIBERATE
----------------------------------------------------
Natural Earth draws the Line of Control rather than the boundary the
Government of India recognises, so the build script leaves India, Pakistan
and China with no border at all - they carry a neutral land fill, which
depicts terrain and claims nothing. India is drawn separately, one layer
above the globe, from the ISRO Bhuvan (Survey of India) raster that
:mod:`utils.datasources.boundaries` fetches. That layer covers India's full
official extent, Aksai Chin and PoK included, so the frontiers a viewer
actually sees along those margins are the official ones.

If Bhuvan is unreachable, India stays unbordered rather than falling back to
a foreign depiction. No line is better than the wrong line.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from utils.datasources.base import SourceResult, SourceStatus

TEXTURE_PATH = (Path(__file__).resolve().parents[2]
                / "data" / "world" / "earth_texture.png")

ATTRIBUTION = (
    "Coastlines and international boundaries: Natural Earth 1:110m, public "
    "domain. India, and every boundary within the Indian subcontinent, is "
    "drawn from ISRO Bhuvan (Survey of India depiction) and never from this "
    "layer."
)

# Kept in step with tools/build_world_atlas.py. The globe reads these so the
# ocean sphere, the atmosphere rim and the texture agree on one blue.
WATER_HEX = "#124A82"
WATER_DEEP_HEX = "#0B3460"

UNBORDERED = ("India", "Pakistan", "China")

_cached_uri: Optional[str] = None


def texture_data_uri() -> Optional[str]:
    """
    The Earth texture as a browser-ready data URI, or None if it is missing.

    Read once and held, because the file never changes between builds and the
    landing page rebuilds its HTML on every Streamlit rerun.
    """
    global _cached_uri

    if _cached_uri is None:
        if not TEXTURE_PATH.exists():
            return None
        payload = TEXTURE_PATH.read_bytes()
        _cached_uri = ("data:image/png;base64,"
                       + base64.b64encode(payload).decode("ascii"))

    return _cached_uri


def fetch_world_texture() -> SourceResult:
    """
    Describe the texture as a data source, for the Data sources tab.

    Reports LIVE when the committed raster is present: it is a build artefact
    rather than a network fetch, so it is never stale and never partial.
    """
    uri = texture_data_uri()

    if uri is None:
        return SourceResult(
            source="World base map",
            status=SourceStatus.UNAVAILABLE,
            message=(
                "data/world/earth_texture.png is missing. Rebuild it with "
                "`python tools/build_world_atlas.py`. The globe will render "
                "as an unmarked blue sphere until then."
            ),
            citation=ATTRIBUTION,
        )

    size = TEXTURE_PATH.stat().st_size

    return SourceResult(
        source="World base map",
        status=SourceStatus.LIVE,
        data={"data_uri": uri, "path": str(TEXTURE_PATH)},
        valid_time=datetime.fromtimestamp(
            TEXTURE_PATH.stat().st_mtime, tz=timezone.utc
        ).isoformat(timespec="seconds"),
        message=(
            f"Committed 4096x2048 equirectangular raster, {size / 1024:.0f} KB. "
            f"Coastlines, country fills and one blue for all water. "
            f"{', '.join(UNBORDERED)} carry no border here - India is drawn "
            f"from Bhuvan on the layer above."
        ),
        citation=ATTRIBUTION,
        metadata={
            "projection": "EPSG:4326 equirectangular, full globe",
            "geometry": "Natural Earth 1:110m (public domain)",
            "unbordered": list(UNBORDERED),
            "water": WATER_HEX,
            "bytes": size,
        },
    )
