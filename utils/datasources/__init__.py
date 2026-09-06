"""
utils.datasources
Data ingestion for PS 26072: satellite, multiple radars, lightning and model data.

Every source returns a SourceResult carrying explicit provenance, so simulated
and observed data can never be confused in the UI or in training.
"""

from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    haversine_km,
    nearest_radars,
)
from utils.datasources.fusion import FusedObservation, fuse

__all__ = [
    "SourceResult",
    "SourceStatus",
    "FusedObservation",
    "fuse",
    "haversine_km",
    "nearest_radars",
]
