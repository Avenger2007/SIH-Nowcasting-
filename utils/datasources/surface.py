"""
utils/datasources/surface.py
Surface observations - the "atmospheric observation" leg of PS 26072.

Two providers, in preference order:

  OpenWeatherMap  Needs a free API key. Gives the current synoptic observation
                  nearest the point.
  Open-Meteo      No key. Falls back to the analysis field, which is model
                  output rather than a station report - close enough for the
                  surface features, and honestly labelled as such.

Surface data matters here mainly through the dew point depression and the
pressure tendency: a falling pressure with a small dew point depression on a
hot afternoon is the classic pre-convective signature over the Indian plains.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

import config
from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    cache_read,
    cache_write,
    http_get,
    last_error,
    timed,
)


@timed
def fetch_openweather(lat: float, lon: float) -> SourceResult:
    """Current conditions from OpenWeatherMap."""
    api_key = config.get_secret("OPENWEATHER_API_KEY")

    if not config.has_secret("OPENWEATHER_API_KEY"):
        return SourceResult(
            source="OpenWeatherMap surface observation",
            status=SourceStatus.NEEDS_CREDENTIALS,
            message=(
                "No OpenWeatherMap key configured. Free tier gives 1000 "
                "calls/day at openweathermap.org/api. Set OPENWEATHER_API_KEY "
                "in .env."
            ),
            citation="OpenWeatherMap",
        )

    url = f"{config.OPENWEATHER_BASE}/weather"
    response = http_get(url, params={
        "lat": lat, "lon": lon, "appid": api_key, "units": "metric",
    })

    if response is None:
        return SourceResult(
            source="OpenWeatherMap surface observation",
            status=SourceStatus.UNAVAILABLE,
            message=f"OpenWeatherMap request failed: {last_error(url)}",
            citation="OpenWeatherMap",
        )

    try:
        payload = response.json()
        main = payload.get("main", {})
        wind = payload.get("wind", {})

        temperature = float(main.get("temp", 30.0))
        humidity = float(main.get("humidity", 60.0))
        dew_point = _dew_point(temperature, humidity)

        data = {
            "temperature": temperature,
            "humidity": humidity,
            "pressure": float(main.get("pressure", 1006.0)),
            "dew_point": dew_point,
            "dew_point_depression": temperature - dew_point,
            "wind_speed": float(wind.get("speed", 3.0)),
            "wind_deg": float(wind.get("deg", 0.0)),
            "clouds": float(payload.get("clouds", {}).get("all", 50.0)),
            "visibility": float(payload.get("visibility", 10000)) / 1000.0,
            "weather_desc": payload.get("weather", [{}])[0].get(
                "description", "unknown"),
            "station": payload.get("name", ""),
        }

        return SourceResult(
            source="OpenWeatherMap surface observation",
            status=SourceStatus.LIVE,
            data=data,
            valid_time=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            message=(
                f"{data['temperature']:.1f} C, RH {data['humidity']:.0f}%, "
                f"dew point depression {data['dew_point_depression']:.1f} K"
            ),
            citation="OpenWeatherMap current weather API",
        )
    except Exception as exc:
        return SourceResult(
            source="OpenWeatherMap surface observation",
            status=SourceStatus.UNAVAILABLE,
            message=f"Malformed OpenWeatherMap response: {exc}",
            citation="OpenWeatherMap",
        )


@timed
def fetch_surface(lat: float, lon: float,
                  nwp_result: Optional[SourceResult] = None) -> SourceResult:
    """
    Best available surface data.

    Prefers a real station observation; falls back to the NWP analysis, which
    is already being fetched for the convective parameters, so this costs
    nothing extra.
    """
    owm = fetch_openweather(lat, lon)
    if owm.status == SourceStatus.LIVE:
        return owm

    if nwp_result is not None and nwp_result.ok:
        current = nwp_result.data["current"]
        temperature = current["temperature_c"]
        dew_point = current["dew_point_c"]
        data = {
            "temperature": temperature,
            "humidity": current["humidity_pct"],
            "pressure": current["pressure_hpa"],
            "dew_point": dew_point,
            "dew_point_depression": temperature - dew_point,
            "wind_speed": current["wind_speed_10m_ms"],
            "wind_deg": current["wind_dir_10m_deg"],
            "clouds": current["cloud_cover_pct"],
            "visibility": 10.0,
            "weather_desc": "from model analysis",
            "station": "",
        }
        return SourceResult(
            source="Surface analysis (Open-Meteo)",
            status=SourceStatus.LIVE,
            data=data,
            valid_time=nwp_result.valid_time,
            message=(
                f"{temperature:.1f} C, RH {data['humidity']:.0f}% - from the "
                "model analysis, not a station report."
            ),
            citation="Open-Meteo.com surface analysis",
        )

    return SourceResult(
        source="Surface observation",
        status=SourceStatus.UNAVAILABLE,
        message="No surface data source available.",
        citation="none",
    )


def _dew_point(temperature_c: float, humidity_pct: float) -> float:
    """Magnus-Tetens dew point."""
    import math

    a, b = 17.27, 237.7
    humidity = max(min(humidity_pct, 100.0), 1.0)
    alpha = (a * temperature_c) / (b + temperature_c) + math.log(humidity / 100.0)
    return (b * alpha) / (a - alpha)
