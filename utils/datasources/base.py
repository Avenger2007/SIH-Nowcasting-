"""
utils/datasources/base.py
Common contract for every data source.

The original code had no way to tell a real observation from a simulated one:
``generate_sample_satellite_images`` produced random blobs and the dashboard
displayed them under the heading "Latest IR Image". Every source in this package
therefore returns a :class:`SourceResult` that states, unambiguously, where its
numbers came from - and the UI renders that status next to the data.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import config


class SourceStatus(str, Enum):
    """Provenance of a data payload. Displayed verbatim in the UI."""

    LIVE = "live"                  # fetched from the provider just now
    CACHED = "cached"              # from local cache, still within TTL
    STALE = "stale"                # from cache, past TTL, provider unreachable
    SIMULATED = "simulated"        # synthetic stand-in - NOT an observation
    UNAVAILABLE = "unavailable"    # nothing usable was obtained
    NEEDS_CREDENTIALS = "needs_credentials"   # provider requires a key/account


@dataclass
class SourceResult:
    """A payload plus everything needed to judge how much to trust it."""

    source: str                       # e.g. "INSAT-3D / MOSDAC"
    status: SourceStatus
    data: Any = None
    fetched_at: str = ""
    valid_time: Optional[str] = None  # observation time, not fetch time
    message: str = ""
    citation: str = ""
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.fetched_at:
            self.fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    @property
    def ok(self) -> bool:
        """True when the payload is usable at all (real or simulated)."""
        return self.data is not None and self.status not in (
            SourceStatus.UNAVAILABLE,
            SourceStatus.NEEDS_CREDENTIALS,
        )

    @property
    def is_observation(self) -> bool:
        """True only when the payload came from a real provider."""
        return self.status in (
            SourceStatus.LIVE,
            SourceStatus.CACHED,
            SourceStatus.STALE,
        )

    def summary(self) -> Dict[str, Any]:
        """Provenance without the payload - safe to log or render."""
        d = asdict(self)
        d.pop("data", None)
        d["status"] = self.status.value
        d["is_observation"] = self.is_observation
        return d


# --------------------------------------------------------------------------
# Disk cache
# --------------------------------------------------------------------------

def _cache_path(key: str, suffix: str = ".json") -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
    return config.CACHE_DIR / f"{digest}{suffix}"


def cache_read(key: str, ttl: int = config.CACHE_TTL_SECONDS) -> Optional[Dict]:
    """
    Read a cached JSON payload.

    Returns a dict with 'value' and 'expired'. Expired entries are still
    returned so a caller can serve stale data when the provider is down -
    which matters for a warning system that must degrade, not disappear.
    """
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    age = time.time() - payload.get("_cached_at", 0)
    return {
        "value": payload.get("value"),
        "expired": age > ttl,
        "age_seconds": age,
    }


def cache_write(key: str, value: Any) -> None:
    """Persist a JSON-serialisable payload."""
    path = _cache_path(key)
    try:
        path.write_text(
            json.dumps({"_cached_at": time.time(), "value": value}),
            encoding="utf-8",
        )
    except (OSError, TypeError):
        pass  # a cache failure must never break a fetch


def cache_binary_path(key: str, suffix: str) -> Path:
    """Path for a cached binary blob (imagery, GRIB, NetCDF)."""
    return _cache_path(key, suffix)


# --------------------------------------------------------------------------
# HTTP with retry
# --------------------------------------------------------------------------

def http_get(url: str,
             params: Optional[Dict] = None,
             headers: Optional[Dict] = None,
             timeout: int = config.HTTP_TIMEOUT,
             retries: int = config.HTTP_RETRIES,
             stream: bool = False):
    """
    GET with bounded exponential backoff.

    Returns the ``requests.Response`` on success, or None. Never raises -
    an unreachable provider degrades the forecast, it does not crash it.
    """
    import requests

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers=headers or {"User-Agent": "SIH-Nowcasting/2.0"},
                timeout=timeout,
                stream=stream,
            )
            if response.status_code == 200:
                return response
            last_error = f"HTTP {response.status_code}"
            # Client errors will not fix themselves on retry.
            if 400 <= response.status_code < 500 and response.status_code != 429:
                break
        except Exception as exc:  # network, DNS, TLS, timeout
            last_error = str(exc)

        if attempt < retries - 1:
            time.sleep(2 ** attempt)

    _LAST_ERRORS[url] = last_error
    return None


_LAST_ERRORS: Dict[str, Optional[str]] = {}


def last_error(url: str) -> str:
    return _LAST_ERRORS.get(url) or "unknown error"


# --------------------------------------------------------------------------
# Timing helper
# --------------------------------------------------------------------------

def timed(fn: Callable) -> Callable:
    """Decorator recording wall-clock latency onto the returned SourceResult."""

    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        if isinstance(result, SourceResult):
            result.latency_ms = (time.perf_counter() - start) * 1000.0
        return result

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


# --------------------------------------------------------------------------
# Geometry helpers shared by the sources
# --------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    import math

    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_radars(lat: float, lon: float, n: int = 3) -> List[Dict]:
    """The N closest DWR sites to a point, with distance and in-range flag."""
    scored = []
    for station in config.DWR_NETWORK:
        distance = haversine_km(lat, lon, station.lat, station.lon)
        scored.append({
            "code": station.code,
            "city": station.city,
            "lat": station.lat,
            "lon": station.lon,
            "band": station.band,
            "range_km": station.range_km,
            "distance_km": round(distance, 1),
            "in_range": distance <= station.range_km,
        })
    scored.sort(key=lambda s: s["distance_km"])
    return scored[:n]
