"""
utils/satellite.py
Satellite data fetching from MOSDAC/ISRO and sample data generation.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta
import requests


def generate_sample_satellite_images(output_dir: str = "data/sample_images", count: int = 6):
    """
    Generate realistic sample satellite images for demo purposes.
    In production, these come from MOSDAC API (INSAT-3D).
    
    Each image is a simulated IR (infrared) brightness temperature map:
    - Cold regions (white/bright) = high clouds = potential convection
    - Warm regions (dark) = low clouds/ground = no convection
    """
    os.makedirs(output_dir, exist_ok=True)
    
    images = []
    timestamps = []
    
    # Base "cloud field" that evolves over time
    np.random.seed(42)
    
    for i in range(count):
        # Create a 256x256 IR brightness temperature image
        # Simulate convective clouds as cold blobs (low values = cold = high clouds)
        
        img_array = np.ones((256, 256), dtype=np.uint8) * 180  # Warm background
        
        # Add some "convective cells" (cold regions)
        num_cells = np.random.randint(2, 6)
        for _ in range(num_cells):
            cx = np.random.randint(30, 226)
            cy = np.random.randint(30, 226)
            radius = np.random.randint(15, 40)
            intensity = np.random.randint(40, 120)  # How cold (lower = colder = taller cloud)
            
            y, x = np.ogrid[-cx:256-cx, -cy:256-cy]
            mask = x*x + y*y <= radius*radius
            
            # Add some noise for realism
            noise = np.random.normal(0, 10, (256, 256)).astype(np.int16)
            img_array = img_array.astype(np.int16) - (mask * intensity).astype(np.int16) + noise
            img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        
        # Add time-evolving component (clouds move and grow)
        shift = i * 3
        img_array = np.roll(img_array, shift, axis=1)
        img_array = np.roll(img_array, shift // 2, axis=0)
        
        # Make clouds grow over time (convective development)
        if i > 2:
            warm_mask = img_array > 150
            img_array[warm_mask] = (img_array[warm_mask] * 0.95).astype(np.uint8)
        
        img = Image.fromarray(img_array, mode='L')
        
        # Convert to RGB for display
        img_rgb = img.convert('RGB')
        draw = ImageDraw.Draw(img_rgb)
        
        # Add timestamp
        ts = datetime.utcnow() - timedelta(minutes=30 * (count - 1 - i))
        timestamps.append(ts)
        
        # Save
        filename = f"satellite_{ts.strftime('%Y%m%d_%H%M')}.png"
        filepath = os.path.join(output_dir, filename)
        img_rgb.save(filepath)
        images.append(str(filepath))
    
    print(f"✅ Generated {count} sample satellite images in {output_dir}")
    return images, timestamps


def fetch_mosdac_data(username: str, password: str, dataset_id: str = "3SIMG_L1B_STD",
                     start_time: str = None, end_time: str = None, count: int = 10):
    """
    Fetch real INSAT-3D satellite data from MOSDAC API.
    Requires MOSDAC account (free signup at mosdac.gov.in).
    
    Args:
        username: MOSDAC SSO username
        password: MOSDAC SSO password
        dataset_id: Dataset identifier (default: INSAT-3D L1B)
        start_time: Start time in ISO format
        end_time: End time in ISO format
        count: Number of records to download
    
    Returns:
        List of downloaded file paths
    """
    # Using MOSDAC Download API (mdapi)
    # See: https://mosdac.gov.in/downloadapi-manual
    
    config = {
        "user_credentials": {
            "username": username,
            "password": password
        },
        "search_parameters": {
            "datasetId": dataset_id,
            "count": count
        }
    }
    
    if start_time:
        config["search_parameters"]["startTime"] = start_time
    if end_time:
        config["search_parameters"]["endTime"] = end_time
    
    # Save config
    import json
    with open("config_mosdac.json", "w") as f:
        json.dump(config, f, indent=2)
    
    print("📡 MOSDAC config saved. Run 'python mdapi.py' to download.")
    print("   (Requires mdapi.py from https://mosdac.gov.in/software/mdapi.zip)")
    
    return []


def fetch_openweather_data(lat: float, lon: float, api_key: str) -> dict:
    """
    Fetch current weather data from OpenWeatherMap API.
    Used to get temperature, humidity, pressure, wind for feature engineering.
    """
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return {
            "temperature": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "wind_deg": data["wind"].get("deg", 0),
            "clouds": data["clouds"]["all"],
            "visibility": data.get("visibility", 10000),
            "weather_desc": data["weather"][0]["description"],
            "success": True
        }
    except Exception as e:
        print(f"⚠️ OpenWeatherMap API error: {e}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Generate sample data for demo
    images, timestamps = generate_sample_satellite_images()
    print(f"Timestamps: {[t.isoformat() for t in timestamps]}")
