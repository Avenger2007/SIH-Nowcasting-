"""
utils/datasources/fusion.py
Multi-source fusion - where satellite, radar, lightning and model data meet.

This is the module that actually answers PS 26072's "using atmospheric
observation including multiple radars, satellite, lightning and model data".
It fetches every source in parallel, merges them into one named feature
mapping, and - critically - returns a provenance report saying which legs were
real, which were degraded, and which were absent.

A nowcast built from four live sources and one built from a simulator are
different products. The system says which one you are looking at.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

import numpy as np

import config
from utils.datasources import lightning as lightning_src
from utils.datasources import mosdac, nwp, radar, surface
from utils.datasources.base import SourceResult, SourceStatus, nearest_radars

# The four legs the problem statement names, plus surface observations.
REQUIRED_LEGS = ("satellite", "radar", "lightning", "nwp")


@dataclass
class FusedObservation:
    """Everything the model needs, plus everything a judge needs to trust it."""

    features: Dict[str, float] = field(default_factory=dict)
    sources: Dict[str, SourceResult] = field(default_factory=dict)
    location: Dict = field(default_factory=dict)
    valid_time: str = ""

    # -- provenance --------------------------------------------------------

    @property
    def live_legs(self) -> List[str]:
        """Legs backed by a real observation."""
        return [
            name for name in REQUIRED_LEGS
            if name in self.sources and self.sources[name].is_observation
        ]

    @property
    def missing_legs(self) -> List[str]:
        return [name for name in REQUIRED_LEGS if name not in self.live_legs]

    @property
    def coverage_fraction(self) -> float:
        return len(self.live_legs) / len(REQUIRED_LEGS)

    @property
    def has_simulated(self) -> bool:
        return any(
            r.status == SourceStatus.SIMULATED for r in self.sources.values()
        )

    def provenance(self) -> List[Dict]:
        """Per-source provenance, ready to render."""
        rows = []
        for leg, result in self.sources.items():
            rows.append({
                "leg": leg,
                "source": result.source,
                "status": result.status.value,
                "is_observation": result.is_observation,
                "message": result.message,
                "citation": result.citation,
                "latency_ms": round(result.latency_ms, 1),
                "valid_time": result.valid_time,
            })
        return rows

    def confidence_note(self) -> str:
        """One honest sentence about how much this nowcast can be trusted."""
        live, total = len(self.live_legs), len(REQUIRED_LEGS)
        if self.has_simulated:
            return (
                f"{live}/{total} data legs are live observations, and at least "
                "one input is SIMULATED. Treat this as a pipeline "
                "demonstration, not a forecast."
            )
        if live == total:
            return (
                f"All {total} data legs are live observations "
                f"({', '.join(self.live_legs)})."
            )
        return (
            f"{live}/{total} data legs are live ({', '.join(self.live_legs) or 'none'}). "
            f"Missing: {', '.join(self.missing_legs)}. Features for the missing "
            "legs are zero-filled and the nowcast is correspondingly weaker."
        )


def fuse(lat: float,
         lon: float,
         location_name: str = "",
         allow_simulation: bool = True,
         radar_stations: int = 3,
         parallel: bool = True) -> FusedObservation:
    """
    Fetch and merge every data source for a point.

    Sources are fetched concurrently because they are independent network
    calls; a slow radar site should not delay the model data.
    """
    tasks = {
        "nwp": lambda: nwp.fetch_nwp(lat, lon),
        "satellite": lambda: mosdac.fetch_satellite_sequence(
            allow_simulation=allow_simulation),
        "radar": lambda: radar.fetch_radar_mosaic(lat, lon, max_stations=radar_stations),
        "lightning": lambda: lightning_src.fetch_lightning(lat, lon),
    }

    results: Dict[str, SourceResult] = {}
    if parallel:
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            futures = {name: pool.submit(fn) for name, fn in tasks.items()}
            for name, future in futures.items():
                try:
                    results[name] = future.result(timeout=90)
                except Exception as exc:
                    results[name] = SourceResult(
                        source=name,
                        status=SourceStatus.UNAVAILABLE,
                        message=f"Fetch raised: {exc}",
                    )
    else:
        for name, fn in tasks.items():
            try:
                results[name] = fn()
            except Exception as exc:
                results[name] = SourceResult(
                    source=name,
                    status=SourceStatus.UNAVAILABLE,
                    message=f"Fetch raised: {exc}",
                )

    # Surface depends on the NWP result, so it runs after.
    results["surface"] = surface.fetch_surface(lat, lon, results.get("nwp"))

    observation = FusedObservation(
        sources=results,
        location={
            "name": location_name,
            "lat": lat,
            "lon": lon,
            "nearest_radars": nearest_radars(lat, lon, 3),
        },
        valid_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    observation.features = _merge_features(results, lat, lon)
    return observation


def _merge_features(results: Dict[str, SourceResult],
                    lat: float,
                    lon: float) -> Dict[str, float]:
    """
    Build the complete named feature mapping.

    Every leg contributes its features plus an ``*_observed`` indicator, so the
    model can distinguish "no lightning was detected" from "lightning was not
    measured". Silently zero-filling an unobserved channel is how a model
    learns to trust a sensor that is not there.
    """
    features: Dict[str, float] = {}

    # -- NWP / convective parameters --------------------------------------
    nwp_result = results.get("nwp")
    if nwp_result is not None and nwp_result.ok:
        current = nwp_result.data["current"]
        features.update({
            "cape_j_kg": current["cape_j_kg"],
            "cin_j_kg": current["cin_j_kg"],
            "lifted_index": current["lifted_index"],
            "k_index": current["k_index"],
            "total_totals": current["total_totals"],
            "precipitable_water_mm": current["precipitable_water_mm"],
            "deep_layer_shear_ms": current["deep_layer_shear_ms"],
            "lapse_rate_850_500": current["lapse_rate_850_500"],
            "nwp_observed": 1.0,
        })
    else:
        features.update({
            "cape_j_kg": 0.0, "cin_j_kg": 0.0, "lifted_index": 0.0,
            "k_index": 0.0, "total_totals": 0.0,
            "precipitable_water_mm": 0.0, "deep_layer_shear_ms": 0.0,
            "lapse_rate_850_500": 0.0, "nwp_observed": 0.0,
        })

    # -- Radar -------------------------------------------------------------
    radar_result = results.get("radar")
    if radar_result is not None and radar_result.ok:
        radar_features = radar_result.data["features"]
        features.update({
            "max_reflectivity_dbz": radar_features["max_reflectivity_dbz"],
            "mean_reflectivity_dbz": radar_features["mean_reflectivity_dbz"],
            "echo_coverage_fraction": radar_features["echo_coverage_fraction"],
            "convective_fraction": radar_features["convective_fraction"],
            "intense_core_fraction": radar_features["intense_core_fraction"],
            "reflectivity_std": radar_features["reflectivity_std"],
            "radar_station_count": float(len(radar_result.data["stations"])),
            "radar_observed": 1.0,
        })
    else:
        features.update({
            "max_reflectivity_dbz": 0.0, "mean_reflectivity_dbz": 0.0,
            "echo_coverage_fraction": 0.0, "convective_fraction": 0.0,
            "intense_core_fraction": 0.0, "reflectivity_std": 0.0,
            "radar_station_count": 0.0, "radar_observed": 0.0,
        })

    # -- Lightning ---------------------------------------------------------
    lightning_result = results.get("lightning")
    if lightning_result is not None and lightning_result.data:
        features.update(lightning_result.data["features"])
        features["lightning_observed"] = (
            1.0 if lightning_result.is_observation else 0.0
        )
    else:
        features.update(lightning_src.empty_features())
        features["lightning_observed"] = 0.0

    # -- Surface -----------------------------------------------------------
    surface_result = results.get("surface")
    if surface_result is not None and surface_result.ok:
        s = surface_result.data
        features.update({
            "temperature": s["temperature"],
            "humidity": s["humidity"],
            "pressure": s["pressure"],
            "dew_point_depression": s["dew_point_depression"],
            "wind_speed": s["wind_speed"],
            "wind_deg": s["wind_deg"],
            "cloud_cover": s["clouds"],
            "visibility": s["visibility"],
            "surface_observed": 1.0,
        })
    else:
        features.update({
            "temperature": 30.0, "humidity": 60.0, "pressure": 1006.0,
            "dew_point_depression": 10.0, "wind_speed": 3.0, "wind_deg": 0.0,
            "cloud_cover": 50.0, "visibility": 10.0, "surface_observed": 0.0,
        })

    # -- Satellite ---------------------------------------------------------
    # Satellite imagery features come from utils.features, which needs the
    # raster pair; fusion only records whether the leg is an observation.
    satellite_result = results.get("satellite")
    features["satellite_observed"] = (
        1.0 if (satellite_result and satellite_result.is_observation) else 0.0
    )

    return features


def get_satellite_frames(observation: FusedObservation):
    """Extract the Kelvin frame sequence and timestamps from a fused result."""
    result = observation.sources.get("satellite")
    if result is None or not result.ok:
        return [], []
    frames = result.data.get("frames_k") or []
    timestamps = result.data.get("timestamps") or []
    return frames, timestamps
