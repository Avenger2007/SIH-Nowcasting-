# 📡 Real Data Integration Guide
## Thunderstorm & Lightning Nowcasting — SIH26072

This document describes how to integrate **real data sources** into the Thunderstorm Nowcasting system. All sources listed here are **free** and publicly accessible.

---

## 📋 Table of Contents

1. [MOSDAC INSAT-3D Satellite Data](#1-mosdac-insat-3d-satellite-data)
2. [IMD Radar Data](#2-imd-radar-data)
3. [Lightning Data (GLD360)](#3-lightning-data-gld360)
4. [OpenWeatherMap API](#4-openweathermap-api)
5. [Google Earth Engine](#5-google-earth-engine)
6. [Wyoming Weather Soundings](#6-wyoming-weather-soundings)

---

## 1. MOSDAC INSAT-3D Satellite Data

### Overview
- **Source:** Meteorological & Oceanographic Satellite Data Archival Centre (MOSDAC)
- **Website:** https://www.mosdac.gov.in
- **Data:** INSAT-3D and INSAT-3DR geostationary satellite imagery
- **Resolution:** 4 km (IMAGER), 1 km (SOUNDER)
- **Frequency:** Every 30 minutes (IMAGER), every hour (SOUNDER)
- **Spectral Bands:** VIS, SWIR, MIR, TIR-1, TIR-2, WV

### Step-by-Step Access

#### Step 1: Create MOSDAC Account
1. Go to https://mosdac.gov.in/signup/
2. Fill in your details
3. Wait for approval (usually 1-2 days)
4. You'll receive username/password via email

#### Step 2: Download MOSDAC API Client
```bash
# Download mdapi.zip from MOSDAC
wget https://mosdac.gov.in/software/mdapi.zip
unzip mdapi.zip
```

#### Step 3: Configure Download
Create `config.json`:
```json
{
  "user_credentials": {
    "username": "YOUR_MOSDAC_USERNAME",
    "password": "YOUR_MOSDAC_PASSWORD"
  },
  "search_parameters": {
    "datasetId": "3SIMG_L1B_STD",
    "startTime": "2026-09-01T00:00:00",
    "endTime": "2026-09-05T23:59:59",
    "count": 100
  }
}
```

#### Step 4: Run Download
```bash
python mdapi.py
```

### Key Dataset IDs

| Dataset ID | Description | Latency |
|---|---|---|
| `3SIMG_L1B_STD` | INSAT-3D IMAGER L1B | 3 days (general users) |
| `3SRIMG_L1B_STD` | INSAT-3DR IMAGER L1B | 3 days |
| `3SIMG_L1C_INS` | INSAT-3D IMAGER L1C | 3 days |
| `3SIMG_L2B_CMV` | Cloud Motion Vectors | 3 days |
| `3SIMG_L2B_OLR` | Outgoing Longwave Radiation | 3 days |
| `3SIMG_L2B_QPE` | Quantitative Precipitation | 3 days |
| `3SIMG_L2B_SST` | Sea Surface Temperature | 3 days |
| `3SIMG_L2B_FIRE` | Fire Detection | 3 days |

### Python Code Example

```python
import requests
import json
import os

def download_mosdac_data(username, password, dataset_id, start_time, end_time, count=100):
    """
    Download satellite data from MOSDAC API.
    """
    config = {
        "user_credentials": {
            "username": username,
            "password": password
        },
        "search_parameters": {
            "datasetId": dataset_id,
            "startTime": start_time,
            "endTime": end_time,
            "count": count
        }
    }
    
    # Save config
    with open("config_mosdac.json", "w") as f:
        json.dump(config, f, indent=2)
    
    # Run mdapi.py (download from MOSDAC first)
    os.system("python mdapi.py")
    
    print(f"Downloaded {count} files for {dataset_id}")

# Example usage
download_mosdac_data(
    username="your_username",
    password="your_password",
    dataset_id="3SIMG_L1B_STD",
    start_time="2026-09-01T00:00:00",
    end_time="2026-09-05T23:59:59",
    count=50
)
```

### Reading INSAT-3D HDF5 Files

```python
import h5py
import numpy as np

def read_insat3d_hdf5(filepath):
    """
    Read INSAT-3D IMAGER data from HDF5 file.
    Returns: dict with channel data and metadata
    """
    with h5py.File(filepath, 'r') as f:
        # List all datasets
        print("Datasets:", list(f.keys()))
        
        # Read VIS band (visible)
        vis = f['IMG_VIS'][:]
        
        # Read TIR-1 band (thermal infrared)
        tir1 = f['IMG_TIR1'][:]
        
        # Read TIR-2 band
        tir2 = f['IMG_TIR2'][:]
        
        # Read WV band (water vapor)
        wv = f['IMG_WV'][:]
        
        # Metadata
        lat = f['Latitude'][:]
        lon = f['Longitude'][:]
        
        return {
            'vis': vis,
            'tir1': tir1,
            'tir2': tir2,
            'wv': wv,
            'lat': lat,
            'lon': lon
        }

# Example
data = read_insat3d_hdf5('3DIMG_01SEP2026_0000_L1B_STD.h5')
print(f"TIR-1 shape: {data['tir1'].shape}")
```

---

## 2. IMD Radar Data

### Overview
- **Source:** India Meteorological Department (IMD)
- **Website:** https://mausam.imd.gov.in
- **Data:** Doppler Weather Radar (DWR) composites
- **Resolution:** 1 km × 1°
- **Frequency:** Every 10 minutes
- **Coverage:** 50+ radar stations across India

### Access Methods

#### Method 1: Direct Image Download (Public)
```python
import requests
from PIL import Image
from io import BytesIO

def download_imd_radar_image():
    """
    Download latest IMD radar composite image.
    """
    # IMD radar composite URL
    url = "https://mausam.imd.gov.in/imd_latest/contents/radar/radar_composite.gif"
    
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    
    return img

# Example
radar_img = download_imd_radar_image()
radar_img.save('radar_composite.png')
```

#### Method 2: Scrape from IMD Portal
```python
import requests
from bs4 import BeautifulSoup

def scrape_imd_radar_images():
    """
    Scrape radar images from IMD website.
    """
    url = "https://mausam.imd.gov.in/responsive/servicesSatMet.php"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find all radar image links
    radar_images = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        if 'radar' in src.lower():
            radar_images.append(src)
    
    return radar_images
```

### Processing Radar Images

```python
import cv2
import numpy as np

def process_radar_image(image_path):
    """
    Process radar image for feature extraction.
    """
    # Read image
    img = cv2.imread(image_path)
    
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply colormap for precipitation intensity
    # IMD uses: light blue (light rain) → red (heavy rain) → purple (extreme)
    
    # Threshold for heavy precipitation
    _, heavy_rain = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
    
    # Find contours of storm cells
    contours, _ = cv2.findContours(heavy_rain, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract storm cell properties
    storm_cells = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 100:  # Minimum area threshold
            x, y, w, h = cv2.boundingRect(cnt)
            storm_cells.append({
                'x': x, 'y': y, 'width': w, 'height': h,
                'area': area,
                'centroid': (x + w//2, y + h//2)
            })
    
    return storm_cells
```

---

## 3. Lightning Data (GLD360)

### Overview
- **Source:** Vaisala GLD360 (Global Lightning Dataset)
- **Website:** https://www.vaisala.com/en/products/data-subscriptions/gld360
- **Data:** Cloud-to-ground and cloud lightning strikes
- **Coverage:** Global
- **Latency:** Near real-time (< 1 minute)
- **Free Tier:** Limited access for research

### Access Methods

#### Method 1: GLD360 API (Research Access)
```python
import requests
import json
from datetime import datetime, timedelta

def fetch_gld360_lightning(lat, lon, radius_km, start_time, end_time, api_key):
    """
    Fetch lightning data from GLD360 API.
    Requires research license from Vaisala.
    """
    url = "https://api.vaisala.com/gld360/v1/strikes"
    
    params = {
        "lat": lat,
        "lon": lon,
        "radius": radius_km,
        "start": start_time.isoformat(),
        "end": end_time.isoformat(),
        "apikey": api_key
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return data.get('strikes', [])

# Example
strikes = fetch_gld360_lightning(
    lat=28.6139, lon=77.2090, radius_km=100,
    start_time=datetime.utcnow() - timedelta(hours=1),
    end_time=datetime.utcnow(),
    api_key="YOUR_GLD360_API_KEY"
)
```

#### Method 2: Blitzortung (Free Alternative)
```python
import requests
import json

def fetch_blitzortung_lightning(lat, lon, radius_km=100):
    """
    Fetch lightning data from Blitzortung (free, community-driven).
    No API key required.
    """
    url = "https://map.blitzortung.org/Gruppen/bo.php"
    
    params = {
        "lat": lat,
        "lon": lon,
        "zoom": 8,
        "tok": "public"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    # Parse strikes
    strikes = []
    for station in data.get('stations', []):
        strikes.append({
            'lat': station.get('lat'),
            'lon': station.get('lon'),
            'time': station.get('time'),
            'distance': station.get('distance')
        })
    
    return strikes

# Example
lightning = fetch_blitzortung_lightning(28.6139, 77.2090)
print(f"Found {len(lightning)} lightning strikes near Delhi")
```

---

## 4. OpenWeatherMap API

### Overview
- **Source:** OpenWeatherMap
- **Website:** https://openweathermap.org/api
- **Free Tier:** 1,000 calls/day
- **Data:** Current weather, forecasts, historical

### API Endpoints

#### Current Weather
```python
import requests

def get_current_weather(lat, lon, api_key):
    """
    Get current weather data.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    return {
        "temperature": data["main"]["temp"],
        "humidity": data["main"]["humidity"],
        "pressure": data["main"]["pressure"],
        "wind_speed": data["wind"]["speed"],
        "wind_deg": data["wind"].get("deg", 0),
        "clouds": data["clouds"]["all"],
        "visibility": data.get("visibility", 10000),
        "weather_desc": data["weather"][0]["description"]
    }
```

#### 5-Day Forecast (3-hour steps)
```python
def get_forecast(lat, lon, api_key):
    """
    Get 5-day forecast (3-hour intervals).
    """
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    forecasts = []
    for item in data.get('list', []):
        forecasts.append({
            "datetime": item["dt_txt"],
            "temperature": item["main"]["temp"],
            "humidity": item["main"]["humidity"],
            "pressure": item["main"]["pressure"],
            "wind_speed": item["wind"]["speed"],
            "clouds": item["clouds"]["all"],
            "weather": item["weather"][0]["description"],
            "rain_3h": item.get("rain", {}).get("3h", 0)
        })
    
    return forecasts
```

#### Historical Data (paid, but has free tier)
```python
def get_historical_weather(lat, lon, dt, api_key):
    """
    Get historical weather data for a specific datetime.
    """
    url = "https://api.openweathermap.org/data/2.5/onecall/timemachine"
    params = {
        "lat": lat,
        "lon": lon,
        "dt": int(dt.timestamp()),
        "appid": api_key,
        "units": "metric"
    }
    
    response = requests.get(url, params=params)
    return response.json()
```

---

## 5. Google Earth Engine

### Overview
- **Source:** Google Earth Engine
- **Website:** https://earthengine.google.com
- **Data:** Satellite imagery (Landsat, Sentinel, MODIS, INSAT)
- **Free:** For research and non-commercial use
- **Access:** Python API (ee)

### Setup
```bash
pip install earthengine-api
```

### Authentication
```python
import ee

# Initialize (one-time authentication required)
ee.Authenticate()  # Opens browser for Google login
ee.Initialize()
```

### Fetch INSAT-3D Data
```python
def fetch_insat3d_ee(date_start, date_end, geometry):
    """
    Fetch INSAT-3D data from Google Earth Engine.
    """
    # INSAT-3D collection (if available)
    # Note: INSAT data may not be directly on GEE
    # Alternative: Use Himawari-8 (similar geostationary satellite)
    
    # Himawari-8 AHI data
    collection = (ee.ImageCollection('NOAA/HIMAWARI-8/AHI')
                  .filterDate(date_start, date_end)
                  .filterBounds(geometry))
    
    # Get first image
    image = collection.first()
    
    # Select bands
    # Band 13: Clean IR (10.4 μm) - good for cloud top temperature
    # Band 8: Water Vapor (6.2 μm)
    ir_band = image.select('B13')
    
    return ir_band

# Example
geometry = ee.Geometry.Rectangle([76.0, 28.0, 78.0, 29.0])  # Delhi region
ir_image = fetch_insat3d_ee('2026-09-01', '2026-09-05', geometry)
```

### Fetch Rainfall Data (IMERG)
```python
def fetch_imerg_rainfall(date_start, date_end, geometry):
    """
    Fetch IMERG rainfall data from GPM.
    """
    collection = (ee.ImageCollection('NASA/GPM_L3/IMERG_V06')
                  .filterDate(date_start, date_end)
                  .filterBounds(geometry)
                  .select('precipitationCal'))
    
    # Sum over period
    total_rain = collection.sum()
    
    return total_rain
```

---

## 6. Wyoming Weather Soundings

### Overview
- **Source:** University of Wyoming
- **Website:** http://weather.uwyo.edu/upperair/sounding.html
- **Data:** Radiosonde upper air soundings
- **Parameters:** Temperature, humidity, wind at multiple pressure levels
- **Derived:** CAPE, CIN, Lifted Index, K-index

### Access
```python
import requests
from bs4 import BeautifulSoup
import pandas as pd

def fetch_wyoming_sounding(station_id, date):
    """
    Fetch upper air sounding data from Wyoming.
    
    Args:
        station_id: Station ID (e.g., 42182 for Delhi)
        date: datetime object
    
    Returns:
        DataFrame with sounding data
    """
    url = "http://weather.uwyo.edu/cgi-bin/sounding"
    
    params = {
        "region": "naconf",
        "TYPE": "TEXT:LIST",
        "YEAR": date.year,
        "MONTH": date.month,
        "FROM": f"{date.day:02d}{date.hour:02d}",
        "TO": f"{date.day:02d}{date.hour:02d}",
        "STNM": station_id
    }
    
    response = requests.get(url, params=params)
    
    # Parse the text data
    lines = response.text.split('\n')
    
    # Find data section
    data_start = False
    data_lines = []
    for line in lines:
        if 'hPa' in line:  # Header line
            data_start = True
            continue
        if data_start and line.strip():
            data_lines.append(line)
    
    # Parse into DataFrame
    records = []
    for line in data_lines:
        parts = line.split()
        if len(parts) >= 7:
            records.append({
                'pressure': float(parts[0]),
                'height': float(parts[1]),
                'temperature': float(parts[2]),
                'dewpoint': float(parts[3]),
                'rh': float(parts[4]),
                'wind_dir': float(parts[5]),
                'wind_speed': float(parts[6])
            })
    
    return pd.DataFrame(records)

# Example: Delhi sounding
sounding = fetch_wyoming_sounding(42182, datetime(2026, 9, 5, 12, 0))
print(sounding.head())
```

### Calculate CAPE/CIN
```python
import numpy as np

def calculate_cape_cin(sounding_df):
    """
    Calculate CAPE and CIN from sounding data.
    Simplified calculation - for accurate values use MetPy library.
    """
    # Extract arrays
    p = sounding_df['pressure'].values  # hPa
    T = sounding_df['temperature'].values  # °C
    Td = sounding_df['dewpoint'].values  # °C
    
    # Find Lifting Condensation Level (LCL) - simplified
    # Find level where T - Td is minimum near surface
    lcl_idx = np.argmin(T[:10] - Td[:10])
    
    # Find Level of Free Convection (LFC)
    # Find level where parcel temperature > environment temperature
    
    # Find Equilibrium Level (EL)
    # Find level where parcel temperature < environment temperature above LFC
    
    # Simplified CAPE calculation
    # CAPE = g * integral((T_parcel - T_env) / T_env) dz
    
    # For accurate calculation, use MetPy:
    # from metpy.cape_cin import surface_based_cape_cin
    # cape, cin = surface_based_cape_cin(p, T, Td)
    
    # Placeholder values
    cape = 1500  # J/kg (typical for thunderstorms)
    cin = -50    # J/kg (negative = inhibition)
    
    return {
        'cape': cape,
        'cin': cin,
        'lcl_pressure': p[lcl_idx],
        'lcl_height': sounding_df['height'].values[lcl_idx]
    }
```

### Using MetPy for Accurate Calculations
```python
# pip install metpy
from metpy.calc import surface_based_cape_cin, lifted_index
from metpy.units import units
import metpy.calc as mpcalc

def calculate_cape_metpy(sounding_df):
    """
    Calculate CAPE/CIN using MetPy (accurate).
    """
    p = sounding_df['pressure'].values * units.hPa
    T = sounding_df['temperature'].values * units.degC
    Td = sounding_df['dewpoint'].values * units.degC
    
    # Surface-based CAPE/CIN
    cape, cin = surface_based_cape_cin(p, T, Td)
    
    return {
        'cape': cape.magnitude,  # J/kg
        'cin': cin.magnitude     # J/kg
    }
```

---

## 📊 Summary: Data Sources

| Data Source | Type | Cost | Latency | Python Library |
|---|---|---|---|---|
| MOSDAC INSAT-3D | Satellite IR | Free | 3 days | h5py, requests |
| IMD Radar | Radar composite | Free | 10 min | PIL, requests |
| GLD360 | Lightning | Research license | < 1 min | requests |
| Blitzortung | Lightning | Free | < 1 min | requests |
| OpenWeatherMap | Weather | Free (1000/day) | Current | requests |
| Google Earth Engine | Satellite | Free (research) | Hours | earthengine-api |
| Wyoming Soundings | Upper air | Free | 12 hours | requests, MetPy |

---

## 🔄 Integration Workflow

```
1. MOSDAC API → Download INSAT-3D HDF5 → Read with h5py → IR images
2. IMD Portal → Scrape radar images → Process with OpenCV
3. OpenWeatherMap → Current weather → Feature engineering
4. Wyoming Soundings → CAPE/CIN → Feature engineering
5. All features → XGBoost → Thunderstorm probability
6. Probability + Location → LLM → Natural language alert
```

---

*Last updated: September 2026*
