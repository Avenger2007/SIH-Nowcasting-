"""
utils/datasources/lightning.py
Lightning observation ingestion - the "lightning" leg of PS 26072.

Lightning is both a PREDICTOR and a TARGET here:

  * as a predictor, recent strike density and its rate of change are among the
    strongest short-range signals that a cell is electrically active and will
    stay active over the next 30-90 minutes;
  * as a target, strike occurrence in a space-time box is the label the model
    should ultimately be trained against. That is the honest ground truth for
    "lightning nowcasting", and it is what the training pipeline expects.

Available networks for India:

  IITM/ISRO LLN     Indian Institute of Tropical Meteorology lightning network,
                    feeding IMD's public lightning bulletins. Institutional
                    access.
  Blitzortung       Community TOA network with good Indian coverage. Raw strokes
                    require a contributor account (HTTP 401 without one).
  ENTLN / GLD360    Commercial (Earth Networks, Vaisala). IMD is a subscriber.
  ISRO INSAT-3D     No optical lightning imager on INSAT-3D; unlike GOES-16 GLM
                    there is no space-based lightning mapper over India yet.

None of these are open without registration, so this module implements the
adapters and states plainly when credentials are absent, rather than quietly
substituting fake strikes. A local CSV/GeoJSON adapter is provided so a team
with archive data can drop it in and immediately train against real labels.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

import config
from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    haversine_km,
    http_get,
    timed,
)

LIGHTNING_ARCHIVE_DIR = config.DATA_DIR / "lightning"
LIGHTNING_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Feature extraction
# --------------------------------------------------------------------------

def strike_features(strikes: List[Dict],
                    lat: float,
                    lon: float,
                    radius_km: float = 50.0,
                    now: Optional[datetime] = None) -> Dict[str, float]:
    """
    Turn a strike list into model features.

    Args:
        strikes: dicts with 'lat', 'lon', 'time' (ISO string or datetime) and
            optionally 'polarity' and 'type' ('CG' or 'IC').
        lat, lon: centre of the analysis disc.
        radius_km: analysis radius.

    The ratio of intracloud to cloud-to-ground strikes matters: a rapid jump in
    IC activity - the "lightning jump" - often precedes severe weather at the
    surface by 10-20 minutes, which is exactly the nowcasting window.
    """
    now = now or datetime.now(timezone.utc)

    counts = {"total": 0, "cg": 0, "ic": 0}
    recent = {"15min": 0, "30min": 0, "60min": 0}
    distances: List[float] = []

    for strike in strikes:
        try:
            distance = haversine_km(lat, lon, float(strike["lat"]), float(strike["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        if distance > radius_km:
            continue

        timestamp = strike.get("time")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
        if not isinstance(timestamp, datetime):
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        age_min = (now - timestamp).total_seconds() / 60.0
        if age_min < 0 or age_min > 60:
            continue

        counts["total"] += 1
        distances.append(distance)
        if str(strike.get("type", "CG")).upper() == "IC":
            counts["ic"] += 1
        else:
            counts["cg"] += 1

        if age_min <= 15:
            recent["15min"] += 1
        if age_min <= 30:
            recent["30min"] += 1
        recent["60min"] += 1

    area_km2 = np.pi * radius_km ** 2

    # Lightning jump: recent rate versus the preceding half hour.
    rate_recent = recent["15min"] / 15.0
    rate_prior = max(recent["60min"] - recent["15min"], 0) / 45.0
    jump = (rate_recent / rate_prior) if rate_prior > 0.01 else (
        3.0 if rate_recent > 0.1 else 0.0
    )

    return {
        "lightning_strike_count": float(counts["total"]),
        "lightning_cg_count": float(counts["cg"]),
        "lightning_ic_count": float(counts["ic"]),
        "lightning_ic_cg_ratio": float(
            counts["ic"] / counts["cg"] if counts["cg"] else 0.0
        ),
        "lightning_density_per_1000km2": float(
            counts["total"] / area_km2 * 1000.0
        ),
        "lightning_rate_15min": float(recent["15min"]),
        "lightning_rate_30min": float(recent["30min"]),
        "lightning_jump_ratio": float(min(jump, 10.0)),
        "lightning_nearest_km": float(min(distances)) if distances else float(radius_km),
    }


def empty_features(radius_km: float = 50.0) -> Dict[str, float]:
    """Zero-valued features for when no lightning data is available.

    Zero strikes is a meaningful observation ("no lightning nearby"); the
    SourceResult status is what tells the caller whether it was observed or
    merely assumed.
    """
    return strike_features([], 0.0, 0.0, radius_km)


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

@timed
def fetch_blitzortung(lat: float,
                      lon: float,
                      radius_km: float = 50.0) -> SourceResult:
    """
    Blitzortung.org strike feed.

    Raw stroke archives sit behind a contributor login. Without credentials the
    endpoint returns HTTP 401, and this reports NEEDS_CREDENTIALS rather than
    inventing strikes.
    """
    username = config.get_secret("BLITZORTUNG_USER")
    password = config.get_secret("BLITZORTUNG_PASSWORD")

    if not (username and password):
        return SourceResult(
            source="Blitzortung lightning network",
            status=SourceStatus.NEEDS_CREDENTIALS,
            message=(
                "No Blitzortung contributor credentials configured. Set "
                "BLITZORTUNG_USER and BLITZORTUNG_PASSWORD in .env to enable "
                "live strike ingestion."
            ),
            citation="Blitzortung.org community lightning network",
        )

    url = f"{config.BLITZORTUNG_HTTP}/Data/Protected/Strokes/"
    response = http_get(url, headers={"Authorization": "Basic"}, retries=1)

    if response is None:
        return SourceResult(
            source="Blitzortung lightning network",
            status=SourceStatus.UNAVAILABLE,
            message="Authenticated request to Blitzortung failed.",
            citation="Blitzortung.org",
        )

    strikes: List[Dict] = []
    for line in response.text.splitlines():
        try:
            record = json.loads(line)
            strikes.append({
                "lat": record["lat"],
                "lon": record["lon"],
                "time": datetime.fromtimestamp(
                    record["time"] / 1e9, tz=timezone.utc
                ).isoformat(),
                "type": "CG",
            })
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue

    features = strike_features(strikes, lat, lon, radius_km)
    return SourceResult(
        source="Blitzortung lightning network",
        status=SourceStatus.LIVE,
        data={"strikes": strikes, "features": features},
        message=f"{features['lightning_strike_count']:.0f} strikes within "
                f"{radius_km:.0f} km in the last hour",
        citation="Blitzortung.org community lightning network",
    )


@timed
def fetch_local_archive(lat: float,
                        lon: float,
                        radius_km: float = 50.0,
                        path: Optional[Path] = None,
                        now: Optional[datetime] = None) -> SourceResult:
    """
    Read strikes from a local CSV or GeoJSON archive.

    This is the adapter a team should use for TRAINING. Drop an IITM/ENTLN
    export into ``data/lightning/`` with columns ``time,lat,lon[,type]`` and the
    pipeline gains real labels immediately.
    """
    directory = path or LIGHTNING_ARCHIVE_DIR
    files = sorted(directory.glob("*.csv")) + sorted(directory.glob("*.geojson"))

    if not files:
        return SourceResult(
            source="Local lightning archive",
            status=SourceStatus.UNAVAILABLE,
            message=(
                f"No lightning archive found in {directory.name}/. Drop a CSV "
                "with columns time,lat,lon[,type] there to enable real "
                "lightning labels for training."
            ),
            citation="Local archive",
        )

    strikes: List[Dict] = []
    for file in files:
        try:
            if file.suffix == ".csv":
                with file.open(newline="", encoding="utf-8") as handle:
                    for row in csv.DictReader(handle):
                        strikes.append({
                            "lat": row.get("lat") or row.get("latitude"),
                            "lon": row.get("lon") or row.get("longitude"),
                            "time": row.get("time") or row.get("timestamp"),
                            "type": row.get("type", "CG"),
                        })
            else:
                payload = json.loads(file.read_text(encoding="utf-8"))
                for feature in payload.get("features", []):
                    coords = feature.get("geometry", {}).get("coordinates", [None, None])
                    props = feature.get("properties", {})
                    strikes.append({
                        "lon": coords[0],
                        "lat": coords[1],
                        "time": props.get("time"),
                        "type": props.get("type", "CG"),
                    })
        except Exception:
            continue

    features = strike_features(strikes, lat, lon, radius_km, now=now)
    return SourceResult(
        source=f"Local lightning archive ({len(files)} file"
               f"{'s' if len(files) != 1 else ''})",
        status=SourceStatus.LIVE,
        data={"strikes": strikes, "features": features},
        message=f"{features['lightning_strike_count']:.0f} strikes within "
                f"{radius_km:.0f} km in the last hour "
                f"(from {len(strikes)} archived records)",
        citation="Local lightning archive",
    )


@timed
def fetch_lightning(lat: float,
                    lon: float,
                    radius_km: float = 50.0) -> SourceResult:
    """
    Best available lightning observation, in preference order.

    Local archive first (a team's own data beats anything), then Blitzortung.
    If nothing is available this returns UNAVAILABLE carrying zeroed features
    so the pipeline still runs - and the UI states that lightning is not being
    observed rather than implying a quiet sky.
    """
    archive = fetch_local_archive(lat, lon, radius_km)
    if archive.status == SourceStatus.LIVE:
        return archive

    blitz = fetch_blitzortung(lat, lon, radius_km)
    if blitz.status == SourceStatus.LIVE:
        return blitz

    return SourceResult(
        source="Lightning network",
        status=SourceStatus.UNAVAILABLE,
        data={"strikes": [], "features": empty_features(radius_km)},
        message=(
            "No lightning network connected. Indian networks (IITM/ISRO, "
            "ENTLN, GLD360) all require institutional access; see "
            "REAL_DATA_INTEGRATION.md. Lightning features are zero-filled and "
            "the model is told they are unobserved."
        ),
        citation="No provider configured",
        metadata={
            "providers_tried": ["local archive", "Blitzortung"],
            "archive_hint": str(LIGHTNING_ARCHIVE_DIR),
        },
    )


# --------------------------------------------------------------------------
# Labels for training
# --------------------------------------------------------------------------

def build_labels(strikes: List[Dict],
                 sample_times: List[datetime],
                 lat: float,
                 lon: float,
                 radius_km: float = 25.0,
                 lead_hours: float = 3.0,
                 min_strikes: int = 1) -> np.ndarray:
    """
    Build the binary nowcasting target from observed strikes.

    A sample at time t is labelled 1 when at least ``min_strikes`` strikes occur
    within ``radius_km`` of the point during (t, t + lead_hours]. This is the
    standard event definition for lightning nowcasting verification, and it is
    what makes POD/FAR/CSI meaningful.

    Note the strictly forward-looking window: including strikes at or before t
    would leak the answer into the features and inflate every score.
    """
    times: List[datetime] = []
    positions: List[tuple] = []

    for strike in strikes:
        timestamp = strike.get("time")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
        if not isinstance(timestamp, datetime):
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        try:
            distance = haversine_km(lat, lon, float(strike["lat"]), float(strike["lon"]))
        except (KeyError, TypeError, ValueError):
            continue
        if distance <= radius_km:
            times.append(timestamp)
            positions.append((distance,))

    times_array = np.array([t.timestamp() for t in times]) if times else np.array([])

    labels = np.zeros(len(sample_times), dtype=int)
    window = lead_hours * 3600.0

    for i, sample_time in enumerate(sample_times):
        if sample_time.tzinfo is None:
            sample_time = sample_time.replace(tzinfo=timezone.utc)
        start = sample_time.timestamp()
        if times_array.size:
            in_window = np.sum(
                (times_array > start) & (times_array <= start + window)
            )
            labels[i] = int(in_window >= min_strikes)

    return labels
