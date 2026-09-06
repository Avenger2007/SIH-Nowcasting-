"""
config.py
Central configuration for the thunderstorm nowcasting system.

All tunable constants, data-source endpoints and credential lookups live here so
that no module has to hard-code a threshold or an API host.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

try:  # optional dependency, absence must not break imports
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a convenience only
    pass


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
SAMPLE_IMAGE_DIR = DATA_DIR / "sample_images"
MODEL_DIR = ROOT / "models"
MODEL_PATH = MODEL_DIR / "xgb_model.json"
FRONTEND_DIR = ROOT / "frontend"
ISSUES_PATH = ROOT / "ISSUES.json"

for _d in (DATA_DIR, CACHE_DIR, SAMPLE_IMAGE_DIR, MODEL_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Credentials (never hard-code - read from environment / .env / st.secrets)
# --------------------------------------------------------------------------

def get_secret(name: str, default: str = "") -> str:
    """
    Resolve a secret from Streamlit secrets first, then the environment.

    Streamlit is imported lazily so that CLI and test usage never require it.
    """
    try:
        import streamlit as st

        if hasattr(st, "secrets") and name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def has_secret(name: str) -> bool:
    """True when a secret is present and is not an obvious placeholder."""
    value = get_secret(name).strip()
    if not value:
        return False
    lowered = value.lower()
    placeholders = ("xxx", "your_", "_here", "***", "changeme", "placeholder")
    return not any(p in lowered for p in placeholders)


# --------------------------------------------------------------------------
# Infrared brightness-temperature calibration
# --------------------------------------------------------------------------
# INSAT-3D TIR-1 (10.8 um) products are distributed as counts or as Kelvin.
# 8-bit browse imagery maps a temperature range linearly onto 0-255. Every
# physical threshold in this project is expressed in KELVIN and converted at
# the boundary, so an 8-bit PNG and a calibrated NetCDF give the same answer.

BT_MIN_K = 180.0   # top of the scale: coldest overshooting tops
BT_MAX_K = 320.0   # bottom of the scale: hot land surface

# Convective thresholds in Kelvin (standard IR nowcasting values)
BT_CONVECTIVE_K = 241.0        # ~ -32 C, cumulonimbus anvil
BT_DEEP_CONVECTIVE_K = 221.0   # ~ -52 C, deep convection / likely lightning
BT_OVERSHOOT_K = 205.0         # ~ -68 C, overshooting top

# Cooling rate that indicates vigorous vertical growth (K per minute)
RAPID_COOLING_K_PER_MIN = 0.25


# --------------------------------------------------------------------------
# Nowcasting parameters
# --------------------------------------------------------------------------

SATELLITE_INTERVAL_MIN = 30.0   # INSAT-3D full-disk imager cadence
LEAD_TIMES_HOURS = (1, 2, 3, 4, 5, 6)
GRID_SIZE = 256                 # working raster size


# --------------------------------------------------------------------------
# Risk banding
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskBand:
    name: str
    minimum: float
    color: str
    hex: str


RISK_BANDS: Tuple[RiskBand, ...] = (
    RiskBand("HIGH", 70.0, "red", "#ff3b52"),
    RiskBand("MODERATE", 40.0, "orange", "#ff8c1a"),
    RiskBand("LOW", 20.0, "yellow", "#ffc531"),
    RiskBand("MINIMAL", 0.0, "green", "#2ecc71"),
)


def classify_risk(probability: float) -> RiskBand:
    """Map a 0-100 probability onto a risk band."""
    for band in RISK_BANDS:
        if probability >= band.minimum:
            return band
    return RISK_BANDS[-1]


# --------------------------------------------------------------------------
# Indian observation network - used by the ingestion layer and the 3D globe
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Satellite:
    """A meteorological satellite relevant to Indian nowcasting."""
    name: str
    operator: str
    longitude: float          # sub-satellite longitude, degrees East
    altitude_km: float
    instruments: Tuple[str, ...]
    status: str
    note: str = ""


SATELLITES: Tuple[Satellite, ...] = (
    Satellite("INSAT-3D", "ISRO", 82.0, 35786,
              ("IMAGER (6 band)", "SOUNDER (19 channel)"), "operational",
              "Primary IR/WV source. 4 km TIR, 30 min full disk."),
    Satellite("INSAT-3DR", "ISRO", 74.0, 35786,
              ("IMAGER (6 band)", "SOUNDER (19 channel)"), "operational",
              "Staggered with 3D to give an effective 15 min cadence."),
    Satellite("INSAT-3DS", "ISRO", 82.0, 35786,
              ("IMAGER (6 band)", "SOUNDER (19 channel)"), "operational",
              "Launched Feb 2024. Successor payload to INSAT-3D."),
    Satellite("KALPANA-1", "ISRO", 74.0, 35786,
              ("VHRR",), "decommissioned",
              "Retired 2017. Listed for archive reprocessing only."),
    Satellite("SCATSAT-1", "ISRO", 0.0, 720,
              ("OSCAT scatterometer",), "archive",
              "Polar orbit. Ocean surface winds for boundary forcing."),
    Satellite("Megha-Tropiques", "ISRO/CNES", 0.0, 867,
              ("MADRAS", "SAPHIR", "ScaRaB"), "archive",
              "Tropical humidity and convection archive."),
)


@dataclass(frozen=True)
class RadarStation:
    """An IMD Doppler Weather Radar site."""
    code: str
    city: str
    lat: float
    lon: float
    band: str
    range_km: int = 250


# IMD Doppler Weather Radar network (representative operational subset).
DWR_NETWORK: Tuple[RadarStation, ...] = (
    RadarStation("DEL", "Delhi (Palam)", 28.5665, 77.1031, "S"),
    RadarStation("MUM", "Mumbai (Colaba)", 18.9067, 72.8147, "S"),
    RadarStation("CHN", "Chennai", 13.0060, 80.1800, "S"),
    RadarStation("KOL", "Kolkata", 22.6531, 88.4467, "S"),
    RadarStation("NAG", "Nagpur", 21.1000, 79.0500, "S"),
    RadarStation("HYD", "Hyderabad", 17.4530, 78.4670, "S"),
    RadarStation("JAI", "Jaipur", 26.8180, 75.8020, "S"),
    RadarStation("LKO", "Lucknow", 26.7600, 80.8800, "S"),
    RadarStation("PAT", "Patna", 25.5940, 85.0870, "S"),
    RadarStation("BHO", "Bhopal", 23.2870, 77.3370, "S"),
    RadarStation("AHM", "Ahmedabad", 23.0630, 72.6320, "S"),
    RadarStation("GOA", "Goa", 15.4840, 73.8180, "S"),
    RadarStation("VIS", "Visakhapatnam", 17.7210, 83.2240, "S"),
    RadarStation("MCH", "Machilipatnam", 16.2000, 81.1500, "S"),
    RadarStation("SHR", "Sriharikota", 13.6600, 80.2300, "S"),
    RadarStation("KAR", "Karaikal", 10.9200, 79.8300, "S"),
    RadarStation("KOC", "Kochi", 9.9500, 76.2700, "S"),
    RadarStation("THI", "Thiruvananthapuram", 8.4800, 76.9500, "C"),
    RadarStation("BNG", "Bengaluru", 13.1990, 77.7060, "S"),
    RadarStation("MOH", "Mohanbari", 27.4800, 95.0200, "S"),
    RadarStation("AGT", "Agartala", 23.8870, 91.2400, "S"),
    RadarStation("PDP", "Paradip", 20.3160, 86.6110, "S"),
    RadarStation("GOP", "Gopalpur", 19.2700, 84.9100, "S"),
    RadarStation("BHJ", "Bhuj", 23.2400, 69.6700, "S"),
    RadarStation("PTL", "Patiala", 30.3300, 76.4000, "C"),
    RadarStation("KUF", "Kufri (Shimla)", 31.0970, 77.2680, "X"),
    RadarStation("MUK", "Mukteshwar", 29.4700, 79.6500, "X"),
    RadarStation("JOT", "Jot (Chamba)", 32.5500, 76.0300, "X"),
    RadarStation("MUR", "Murari Devi", 31.4600, 77.0500, "X"),
    RadarStation("SRN", "Srinagar", 34.0800, 74.8000, "X"),
    RadarStation("JMU", "Jammu", 32.7300, 74.8700, "X"),
    RadarStation("DDN", "Dehradun (Surkanda)", 30.4100, 78.2900, "X"),
    RadarStation("GHY", "Guwahati", 26.1060, 91.5860, "S"),
    RadarStation("VER", "Veravali", 19.1200, 72.8500, "C"),
    RadarStation("LAN", "Lansdowne", 29.8400, 78.6800, "X"),
    RadarStation("CHE", "Cherrapunji", 25.2700, 91.7300, "X"),
)


@dataclass(frozen=True)
class City:
    name: str
    lat: float
    lon: float
    state: str


CITIES: Tuple[City, ...] = (
    City("Delhi", 28.6139, 77.2090, "Delhi"),
    City("Mumbai", 19.0760, 72.8777, "Maharashtra"),
    City("Kolkata", 22.5726, 88.3639, "West Bengal"),
    City("Chennai", 13.0827, 80.2707, "Tamil Nadu"),
    City("Bengaluru", 12.9716, 77.5946, "Karnataka"),
    City("Hyderabad", 17.3850, 78.4867, "Telangana"),
    City("Pune", 18.5204, 73.8567, "Maharashtra"),
    City("Ahmedabad", 23.0225, 72.5714, "Gujarat"),
    City("Jaipur", 26.9124, 75.7873, "Rajasthan"),
    City("Lucknow", 26.8467, 80.9462, "Uttar Pradesh"),
    City("Patna", 25.6093, 85.1376, "Bihar"),
    City("Bhopal", 23.2599, 77.4126, "Madhya Pradesh"),
    City("Guwahati", 26.1445, 91.7362, "Assam"),
    City("Imphal", 24.8170, 93.9368, "Manipur"),
    City("Shillong", 25.5788, 91.8933, "Meghalaya"),
    City("Aizawl", 23.7271, 92.7176, "Mizoram"),
    City("Kohima", 25.6751, 94.1086, "Nagaland"),
    City("Gangtok", 27.3389, 88.6065, "Sikkim"),
    City("Agartala", 23.8315, 91.2868, "Tripura"),
    City("Ranchi", 23.3441, 85.3096, "Jharkhand"),
    City("Bhubaneswar", 20.2961, 85.8245, "Odisha"),
    City("Raipur", 21.2514, 81.6296, "Chhattisgarh"),
    City("Dehradun", 30.3165, 78.0322, "Uttarakhand"),
    City("Amaravati", 16.5730, 80.3570, "Andhra Pradesh"),
    City("Thiruvananthapuram", 8.5241, 76.9366, "Kerala"),
    City("Chandigarh", 30.7333, 76.7794, "Punjab/Haryana"),
    City("Srinagar", 34.0837, 74.7973, "J&K"),
    City("Nagpur", 21.1458, 79.0882, "Maharashtra"),
)


CITY_LOOKUP: Dict[str, City] = {c.name: c for c in CITIES}


def get_city(name: str) -> City:
    """Look up a city, defaulting to Delhi."""
    return CITY_LOOKUP.get(name, CITY_LOOKUP["Delhi"])


# --------------------------------------------------------------------------
# Data source endpoints
# --------------------------------------------------------------------------

MOSDAC_BASE = "https://www.mosdac.gov.in"
MOSDAC_ORDER_API = MOSDAC_BASE + "/apiorder/order"
IMD_RADAR_BASE = "https://mausam.imd.gov.in/Radar"
NOMADS_GFS_BASE = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
OPENWEATHER_BASE = "https://api.openweathermap.org/data/2.5"
BLITZORTUNG_HTTP = "https://data.blitzortung.org"

# Bounding box for the Indian region (lon_min, lat_min, lon_max, lat_max)
INDIA_BBOX = (66.0, 6.0, 98.0, 38.0)

CACHE_TTL_SECONDS = 15 * 60
HTTP_TIMEOUT = 20
HTTP_RETRIES = 3
