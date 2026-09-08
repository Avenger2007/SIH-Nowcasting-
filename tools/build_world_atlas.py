"""
tools/build_world_atlas.py
Build the equirectangular Earth texture used by the landing-page globe.

RUN THIS ONLY WHEN THE TEXTURE NEEDS REGENERATING. The output PNG is committed
to the repository so that neither the app nor a deployment ever depends on
reaching a third-party host at runtime.

    python tools/build_world_atlas.py

WHAT IT DRAWS
-------------
  water        one blue, covering ocean, seas, gulfs and inland water
  land         every landmass, from coastlines
  countries    a filled colour per country, plus a boundary stroke

HOW COUNTRY COLOURS ARE CHOSEN
------------------------------
Adjacent countries must never share a colour or the boundary between them
disappears at globe scale. Adjacency is derived from the geometry itself -
two countries are neighbours when they place vertices in the same cell of a
one-degree grid - and the graph is then greedily coloured. The four colour
theorem says four suffice; eight are used so the map has some variety.

INDIA, PAKISTAN AND CHINA ARE DELIBERATELY LEFT UNBORDERED
----------------------------------------------------------
Natural Earth, like OpenStreetMap and GADM, draws the Line of Control rather
than the boundary the Government of India recognises, and the polygons for
India, Pakistan and China all run along a frontier India contests. None of
those three is given a border here. They keep the neutral land fill taken
from the coastline layer, which depicts terrain and claims nothing.

India is then drawn by the globe itself, one layer above the sphere, from the
official ISRO Bhuvan (Survey of India) raster that utils/datasources/
boundaries.py fetches. That raster covers India's full official extent - Aksai
Chin and PoK included - so the frontiers a viewer actually sees along those
margins are the official ones.

If Bhuvan is unreachable India simply stays unbordered, which is the correct
failure: no line is better than the wrong line.

Source of the base geometry:
    Natural Earth, 1:110m, public domain (naturalearthdata.com)
"""

from __future__ import annotations

import json
import math
import sys
import urllib.request
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "world"
OUT_PNG = OUT_DIR / "earth_texture.png"

NE_BASE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
           "master/geojson/")
COUNTRIES_FILE = "ne_110m_admin_0_countries.geojson"
LAND_FILE = "ne_110m_land.geojson"

# The three countries whose Natural Earth outline runs along a frontier India
# contests, and which are therefore never drawn with a border:
#
#   India     the whole point - its official extent comes from Bhuvan instead
#   Pakistan  its polygon takes in Gilgit-Baltistan and what India calls PoK
#   China     its polygon takes in Aksai Chin and stops short of Arunachal
#
# Everything else in the neighbourhood - Nepal, Bhutan, Bangladesh, Myanmar,
# Afghanistan - is drawn normally, because none of those borders is contested
# and Natural Earth already draws them where India does.
#
# The three left out keep the neutral land fill, so they read as terrain with
# no line through it. The Bhuvan raster composited at runtime then covers
# India's official extent, which includes Aksai Chin and PoK, so the borders
# that finally appear along those frontiers are the Survey of India ones.
EXCLUDED_FROM_BORDERS = {"India", "Pakistan", "China"}

# Rendered at this size, then downsampled by SUPERSAMPLE for clean edges.
TEX_W, TEX_H = 4096, 2048
SUPERSAMPLE = 2

WATER = (18, 74, 130)           # one blue for every water body
WATER_DEEP = (11, 52, 96)       # a deeper blue away from the tropics
LAND_NEUTRAL = (172, 185, 166)  # land with no country colour of its own
COASTLINE = (222, 238, 255)
BORDER_INK = (28, 44, 62)

# Eight fills. These were pastels to begin with and the globe washed them out
# to a uniform pale grey the moment any light hit it, which lost exactly the
# thing they are for. They are saturated enough now to stay separable at the
# far edge of the sphere, and still far enough apart in hue that no two
# neighbours read as one country.
PALETTE: Sequence[Tuple[int, int, int]] = (
    (228, 168, 100),   # sand
    (110, 186, 142),   # sage
    (226, 128, 120),   # rose
    (150, 138, 214),   # lilac
    (232, 198, 92),    # wheat
    (86, 180, 168),    # teal
    (216, 134, 186),   # pink
    (158, 198, 96),    # lime
)


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def rings_of(geometry: Dict) -> List[List[Tuple[float, float]]]:
    """Flatten a GeoJSON Polygon or MultiPolygon into a list of rings."""
    kind = geometry.get("type")
    if kind == "Polygon":
        polygons = [geometry["coordinates"]]
    elif kind == "MultiPolygon":
        polygons = geometry["coordinates"]
    else:
        return []

    out: List[List[Tuple[float, float]]] = []
    for polygon in polygons:
        for ring in polygon:
            if len(ring) >= 3:
                out.append([(float(x), float(y)) for x, y in ring])
    return out


def project(ring: Sequence[Tuple[float, float]], width: int, height: int,
            lon_shift: float = 0.0) -> List[Tuple[float, float]]:
    """Equirectangular: longitude to x, latitude to y."""
    return [
        (((lon + lon_shift) + 180.0) / 360.0 * width,
         (90.0 - lat) / 180.0 * height)
        for lon, lat in ring
    ]


def draw_ring(draw: ImageDraw.ImageDraw, ring: Sequence[Tuple[float, float]],
              width: int, height: int, fill=None, outline=None,
              stroke: int = 0) -> None:
    """
    Paint one ring, repeating it across the antimeridian when it wraps.

    Two things that look like a wrap are not one, and both were drawn twice
    before this was tightened:

    * A wide total span. The Afro-Eurasian landmass covers 198 degrees of
      longitude in a single continuous ring, and Antarctica covers the full
      360. Testing the span smeared both into bands right across the map.
    * The segment that closes a circumpolar ring. Antarctica runs east to
      +180, then steps to -180 along the bottom edge to close itself. That is
      a jump of a whole turn between consecutive vertices, but it crosses the
      pole rather than the dateline, and the ring needs drawing only once.

    What is left - a jump of more than half a turn between two consecutive
    vertices away from the poles - is a genuine dateline split, and both
    halves have to be placed.
    """
    def is_wrap(a, b):
        if abs(b[0] - a[0]) <= 180.0:
            return False
        return not (abs(a[1]) >= 89.5 and abs(b[1]) >= 89.5)

    wraps = any(is_wrap(ring[i], ring[i + 1]) for i in range(len(ring) - 1))

    shifts = [0.0]
    if wraps:
        ring = [(lon + 360.0 if lon < 0 else lon, lat) for lon, lat in ring]
        shifts = [0.0, -360.0]

    for shift in shifts:
        points = project(ring, width, height, shift)
        if fill is not None:
            draw.polygon(points, fill=fill)
        if outline is not None and stroke > 0:
            draw.line(points + [points[0]], fill=outline,
                      width=stroke, joint="curve")


# --------------------------------------------------------------------------
# adjacency and colouring
# --------------------------------------------------------------------------

def adjacency(features: List[Dict], cell: float = 1.0) -> Dict[int, set]:
    """
    Which countries touch which, inferred from shared grid cells.

    Exact polygon intersection is not needed: at 1:110m two countries sharing
    a border inevitably drop vertices into the same one-degree cell, and a
    few false neighbours only make the colouring more conservative.
    """
    buckets: Dict[Tuple[int, int], set] = {}
    for index, feature in enumerate(features):
        for ring in rings_of(feature["geometry"]):
            for lon, lat in ring:
                cx = int(math.floor(lon / cell))
                cy = int(math.floor(lat / cell))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        buckets.setdefault((cx + dx, cy + dy), set()).add(index)

    neighbours: Dict[int, set] = {i: set() for i in range(len(features))}
    for members in buckets.values():
        if len(members) < 2:
            continue
        for member in members:
            neighbours[member].update(members - {member})
    return neighbours


def colour_map(features: List[Dict]) -> Dict[int, int]:
    """Greedy graph colouring, most-constrained country first."""
    neighbours = adjacency(features)
    order = sorted(range(len(features)), key=lambda i: -len(neighbours[i]))

    assigned: Dict[int, int] = {}
    for index in order:
        taken = {assigned[n] for n in neighbours[index] if n in assigned}
        for slot in range(len(PALETTE)):
            if slot not in taken:
                assigned[index] = slot
                break
        else:
            assigned[index] = len(assigned) % len(PALETTE)
    return assigned


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def load_layer(name: str) -> Dict:
    """Read a Natural Earth layer, downloading it once into data/world."""
    path = OUT_DIR / name
    if not path.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"  downloading {name} ...")
        with urllib.request.urlopen(NE_BASE + name, timeout=120) as response:
            path.write_bytes(response.read())
    return json.loads(path.read_text(encoding="utf-8"))


def build() -> Path:
    width, height = TEX_W * SUPERSAMPLE, TEX_H * SUPERSAMPLE

    land = load_layer(LAND_FILE)
    countries = load_layer(COUNTRIES_FILE)

    features = [f for f in countries["features"]
                if f["properties"]["NAME"] not in EXCLUDED_FROM_BORDERS]
    print(f"  {len(features)} countries drawn, "
          f"{len(countries['features']) - len(features)} left unbordered")

    slots = colour_map(features)

    image = Image.new("RGB", (width, height), WATER_DEEP)
    draw = ImageDraw.Draw(image)

    # A warmer blue through the tropics keeps a flat ocean from reading as a
    # dead surface once the globe is lit.
    for row in range(height):
        latitude = 90.0 - (row / height) * 180.0
        weight = math.cos(math.radians(latitude)) ** 2
        draw.line(
            [(0, row), (width, row)],
            fill=tuple(int(round(WATER_DEEP[c]
                                 + (WATER[c] - WATER_DEEP[c]) * weight))
                       for c in range(3)),
        )

    # Every landmass first, so the countries left unbordered still read as
    # land rather than as holes in the ocean.
    for feature in land["features"]:
        for ring in rings_of(feature["geometry"]):
            draw_ring(draw, ring, width, height, fill=LAND_NEUTRAL)

    # Country fills.
    for index, feature in enumerate(features):
        colour = PALETTE[slots[index]]
        for ring in rings_of(feature["geometry"]):
            draw_ring(draw, ring, width, height, fill=colour)

    # Boundary strokes last, so no fill paints over a border.
    stroke = max(2, round(2.0 * SUPERSAMPLE))
    for feature in features:
        for ring in rings_of(feature["geometry"]):
            draw_ring(draw, ring, width, height,
                      outline=BORDER_INK, stroke=stroke)

    # Coastlines separate land from water everywhere, including around the
    # countries that carry no border of their own.
    for feature in land["features"]:
        for ring in rings_of(feature["geometry"]):
            draw_ring(draw, ring, width, height,
                      outline=COASTLINE, stroke=max(1, SUPERSAMPLE))

    image = image.resize((TEX_W, TEX_H), Image.LANCZOS)
    image = image.filter(ImageFilter.UnsharpMask(radius=1.2, percent=45))

    # The whole map is flat fills and thin strokes, so a 128-entry palette is
    # visually identical to full colour and roughly a third of the bytes -
    # which matters, because the texture reaches the browser inlined as a
    # data URI.
    image = image.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    image.save(OUT_PNG, optimize=True)
    return OUT_PNG


if __name__ == "__main__":
    print("Building the Earth texture ...")
    written = build()
    print(f"  wrote {written} "
          f"({written.stat().st_size / 1024:.0f} KB, {TEX_W}x{TEX_H})")
    sys.exit(0)
