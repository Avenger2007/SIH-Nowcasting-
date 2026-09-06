"""
utils/features.py
Feature engineering for thunderstorm prediction.
Extracts meteorological features from satellite imagery and weather data.
"""

import numpy as np
import cv2
from typing import Dict, List, Optional
from datetime import datetime


def extract_cloud_top_cooling_features(img: np.ndarray, 
                                        prev_img: np.ndarray,
                                        time_diff_minutes: float = 30.0) -> Dict[str, float]:
    """
    Extract cloud top cooling rate features.
    Rapid cooling = convective development = thunderstorm potential.
    
    In IR satellite imagery:
    - Colder (lower values) = higher cloud tops = taller clouds
    - Rapid cooling = cloud is growing vertically = convection
    
    Args:
        img: Current IR image (0-255, lower = colder)
        prev_img: Previous IR image
        time_diff_minutes: Time difference between images
    
    Returns:
        Dictionary of cooling features
    """
    # Compute brightness temperature change
    bt_change = img.astype(np.float64) - prev_img.astype(np.float64)
    
    # Cooling rate (negative change = cooling = cloud growing)
    cooling_rate = -bt_change / time_diff_minutes  # per minute
    
    # Identify convective regions (colder than threshold)
    cold_threshold = 150  # Adjust based on data
    cold_mask = img < cold_threshold
    
    features = {
        "bt_mean": float(np.mean(img)),
        "bt_std": float(np.std(img)),
        "bt_min": float(np.min(img)),
        "bt_max": float(np.max(img)),
        "bt_gradient_mean": float(np.mean(np.abs(cv2.Sobel(img, cv2.CV_64F, 1, 0)))),
        "bt_gradient_std": float(np.std(cv2.Sobel(img, cv2.CV_64F, 1, 0))),
        "cooling_rate_mean": float(np.mean(cooling_rate)),
        "cooling_rate_max": float(np.max(cooling_rate)),
        "cooling_rate_min": float(np.min(cooling_rate)),
        "cooling_rate_std": float(np.std(cooling_rate)),
        "cold_cloud_fraction": float(np.sum(cold_mask) / cold_mask.size),
        "rapid_cooling_fraction": float(np.sum(cooling_rate > 1.0) / cooling_rate.size),
    }
    
    return features


def extract_texture_features(img: np.ndarray) -> Dict[str, float]:
    """
    Extract texture features from satellite image.
    Convective clouds have distinct texture (rough, cauliflower-like).
    """
    # Local standard deviation (texture measure)
    kernel_size = 5
    local_mean = cv2.blur(img.astype(np.float64), (kernel_size, kernel_size))
    local_sq_mean = cv2.blur((img.astype(np.float64))**2, (kernel_size, kernel_size))
    local_std = np.sqrt(np.maximum(local_sq_mean - local_mean**2, 0))
    
    # Gradient magnitude
    grad_x = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=3)
    grad_y = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
    
    # Laplacian (second derivative - detects edges and blobs)
    laplacian = np.abs(cv2.Laplacian(img, cv2.CV_64F))
    
    features = {
        "texture_mean": float(np.mean(local_std)),
        "texture_std": float(np.std(local_std)),
        "texture_max": float(np.max(local_std)),
        "gradient_mean": float(np.mean(gradient_magnitude)),
        "gradient_std": float(np.std(gradient_magnitude)),
        "gradient_max": float(np.max(gradient_magnitude)),
        "laplacian_mean": float(np.mean(laplacian)),
        "laplacian_std": float(np.std(laplacian)),
    }
    
    return features


def extract_cloud_size_distribution(img: np.ndarray) -> Dict[str, float]:
    """
    Extract cloud size distribution features.
    Large, organized convective systems = higher storm potential.
    """
    # Threshold to identify convective clouds
    threshold = 150
    binary = (img < threshold).astype(np.uint8) * 255
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return {
            "cloud_count": 0,
            "max_cloud_area": 0,
            "mean_cloud_area": 0,
            "total_cloud_fraction": 0,
            "cloud_area_std": 0,
        }
    
    areas = [cv2.contourArea(c) for c in contours]
    
    features = {
        "cloud_count": len(contours),
        "max_cloud_area": float(np.max(areas)),
        "mean_cloud_area": float(np.mean(areas)),
        "total_cloud_fraction": float(np.sum(areas) / img.size),
        "cloud_area_std": float(np.std(areas)),
    }
    
    return features


def extract_temporal_features(timestamps: List[datetime]) -> Dict[str, float]:
    """
    Extract temporal features (diurnal cycle, seasonality).
    Thunderstorms have strong diurnal patterns.
    """
    if not timestamps:
        return {"hour_of_day": 12, "month": 6, "is_afternoon": 1, "is_monsoon": 1}
    
    latest = timestamps[-1]
    hour = latest.hour
    month = latest.month
    
    # Diurnal cycle features
    is_afternoon = 1 if 12 <= hour <= 18 else 0
    is_evening = 1 if 18 <= hour <= 21 else 0
    is_night = 1 if hour >= 21 or hour <= 5 else 0
    
    # Monsoon season (June-September)
    is_monsoon = 1 if 6 <= month <= 9 else 0
    
    # Peak thunderstorm hours (14:00-18:00 IST)
    is_peak_hour = 1 if 14 <= hour <= 18 else 0
    
    features = {
        "hour_of_day": hour,
        "month": month,
        "is_afternoon": is_afternoon,
        "is_evening": is_evening,
        "is_night": is_night,
        "is_monsoon": is_monsoon,
        "is_peak_hour": is_peak_hour,
    }
    
    return features


def extract_weather_features(weather_data: Dict) -> Dict[str, float]:
    """
    Extract features from weather API data.
    """
    features = {
        "temperature": weather_data.get("temperature", 30.0),
        "humidity": weather_data.get("humidity", 70.0),
        "pressure": weather_data.get("pressure", 1013.0),
        "wind_speed": weather_data.get("wind_speed", 5.0),
        "wind_deg": weather_data.get("wind_deg", 0.0),
        "cloud_cover": weather_data.get("clouds", 50.0),
        "visibility": weather_data.get("visibility", 10000.0) / 1000.0,
    }
    
    return features


def build_feature_vector(satellite_img: np.ndarray,
                         prev_satellite_img: np.ndarray,
                         timestamps: List[datetime],
                         weather_data: Optional[Dict] = None,
                         flow_features: Optional[Dict] = None) -> np.ndarray:
    """
    Build complete feature vector for XGBoost prediction.
    
    Args:
        satellite_img: Current satellite image
        prev_satellite_img: Previous satellite image
        timestamps: List of timestamps
        weather_data: Weather API data (optional)
        flow_features: Optical flow features (optional)
    
    Returns:
        Feature vector as numpy array
    """
    features = {}
    
    # Cloud top cooling features
    features.update(extract_cloud_top_cooling_features(satellite_img, prev_satellite_img))
    
    # Texture features
    features.update(extract_texture_features(satellite_img))
    
    # Cloud size distribution
    features.update(extract_cloud_size_distribution(satellite_img))
    
    # Temporal features
    features.update(extract_temporal_features(timestamps))
    
    # Weather features
    if weather_data and weather_data.get("success", False):
        features.update(extract_weather_features(weather_data))
    else:
        # Default values
        features.update({
            "temperature": 30.0, "humidity": 70.0, "pressure": 1013.0,
            "wind_speed": 5.0, "wind_deg": 0.0, "cloud_cover": 50.0,
            "visibility": 10.0
        })
    
    # Flow features
    if flow_features:
        features.update(flow_features)
    else:
        features.update({
            "flow_magnitude_mean": 0.0, "flow_magnitude_std": 0.0,
            "flow_magnitude_max": 0.0, "flow_direction_mean": 0.0,
            "flow_direction_std": 0.0, "convergence_mean": 0.0,
            "convergence_max": 0.0, "convergence_min": 0.0,
            "convergence_std": 0.0
        })
    
    # Convert to vector (sorted by key for consistency)
    feature_names = sorted(features.keys())
    feature_vector = np.array([features[k] for k in feature_names], dtype=np.float32)
    
    return feature_vector, feature_names


if __name__ == "__main__":
    # Test feature extraction
    from satellite import generate_sample_satellite_images
    
    image_paths, timestamps = generate_sample_satellite_images(count=6)
    images = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in image_paths]
    
    # Build feature vector
    feature_vector, feature_names = build_feature_vector(
        images[-1], images[-2], timestamps
    )
    
    print(f"✅ Feature vector built")
    print(f"   Features: {len(feature_names)}")
    print(f"   Vector shape: {feature_vector.shape}")
    print(f"   Feature names: {feature_names}")
