"""
utils/llm_alert.py
LLM-based alert generation using Groq API (Llama 3.1).
Generates natural language thunderstorm alerts for public dissemination.
"""

import os
import json
from typing import Dict, Optional
from datetime import datetime


def generate_alert(prediction: Dict, 
                   location: str = "Delhi",
                   weather_data: Dict = None,
                   api_key: str = None) -> str:
    """
    Generate a natural language thunderstorm alert using Groq LLM.
    
    Args:
        prediction: Dictionary from ThunderstormPredictor.predict_single()
        location: Location name
        weather_data: Weather API data
        api_key: Groq API key (or from env GROQ_API_KEY)
    
    Returns:
        Alert text string
    """
    # Get API key
    api_key = api_key or os.environ.get("GROQ_API_KEY", "")
    
    # If no API key, use template-based alert
    if not api_key or api_key == "***":
        return generate_template_alert(prediction, location, weather_data)
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        # Build prompt
        prompt = build_alert_prompt(prediction, location, weather_data)
        
        response = client.chat.completions.create(
            model="groq/compound",  # Updated: works with this API key
            messages=[
                {
                    "role": "system",
                    "content": "You are a meteorologist at India Meteorological Department. Write concise, clear public weather alerts in English. Keep alerts under 50 words. Use simple language understandable by general public."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=150,
            temperature=0.7,
        )
        
        alert = response.choices[0].message.content.strip()
        return alert
    
    except Exception as e:
        print(f"⚠️ Groq API error: {e}")
        return generate_template_alert(prediction, location, weather_data)


def build_alert_prompt(prediction: Dict, location: str, weather_data: Dict = None) -> str:
    """Build prompt for LLM alert generation."""
    risk_level = prediction["risk_level"]
    probability = prediction["thunderstorm_probability"]
    
    prompt = f"Write a thunderstorm alert for {location}, India.\n"
    prompt += f"Risk Level: {risk_level}\n"
    prompt += f"Probability: {probability:.0f}%\n"
    prompt += f"Lead Time: 0-6 hours\n"
    
    if weather_data and weather_data.get("success", False):
        prompt += f"Current Weather: {weather_data.get('weather_desc', 'unknown')}\n"
        prompt += f"Temperature: {weather_data.get('temperature', 'N/A')}°C\n"
        prompt += f"Humidity: {weather_data.get('humidity', 'N/A')}%\n"
        prompt += f"Wind: {weather_data.get('wind_speed', 'N/A')} m/s\n"
    
    prompt += f"\nInclude: 1) What to expect 2) Safety advice 3) When to expect it"
    
    return prompt


def generate_template_alert(prediction: Dict, location: str, weather_data: Dict = None) -> str:
    """
    Generate alert using templates (no LLM needed).
    Used as fallback when Groq API is not available.
    """
    risk_level = prediction["risk_level"]
    probability = prediction["thunderstorm_probability"]
    
    if risk_level == "HIGH":
        alert = (
            f"⚠️ THUNDERSTORM ALERT for {location}: High probability ({probability:.0f}%) "
            f"of thunderstorm and lightning in the next 0-6 hours. "
            f"Seek shelter immediately if outdoors. Avoid open areas and tall objects. "
            f"Stay tuned to IMD updates."
        )
    elif risk_level == "MODERATE":
        alert = (
            f"⛈️ THUNDERSTORM WATCH for {location}: Moderate probability ({probability:.0f}%) "
            f"of thunderstorm activity in the next 0-6 hours. "
            f"Be prepared to seek shelter. Carry umbrellas and avoid water bodies. "
            f"Monitor weather updates."
        )
    elif risk_level == "LOW":
        alert = (
            f"🌤️ WEATHER ADVISORY for {location}: Low probability ({probability:.0f}%) "
            f"of isolated thunderstorm activity. "
            f"Carry umbrellas when going outdoors. "
            f"Stay aware of changing weather conditions."
        )
    else:
        alert = (
            f"✅ WEATHER UPDATE for {location}: Minimal thunderstorm activity expected. "
            f"Normal weather conditions likely to prevail. "
            f"Enjoy your day!"
        )
    
    return alert


def generate_detailed_report(prediction: Dict,
                              location: str,
                              features: Dict,
                              timestamps: list,
                              api_key: str = None) -> str:
    """
    Generate a detailed meteorological report (for judges/panel).
    """
    report = f"""
# Thunderstorm Nowcasting Report
**Location:** {location}  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} IST  
**Lead Time:** 0-6 hours

## Prediction Summary
| Parameter | Value |
|---|---|
| Thunderstorm Probability | {prediction['thunderstorm_probability']:.1f}% |
| Risk Level | {prediction['risk_level']} |
| Prediction | {'Thunderstorm Expected' if prediction['prediction'] == 1 else 'No Thunderstorm'} |

## Key Features
| Feature | Value |
|---|---|
| Cloud Top Cooling Rate | {features.get('cooling_rate_mean', 'N/A'):.2f} °C/min |
| Cold Cloud Fraction | {features.get('cold_cloud_fraction', 'N/A'):.2%} |
| Cloud Count | {features.get('cloud_count', 'N/A')} |
| Convergence Index | {features.get('convergence_mean', 'N/A'):.2f} |
| Hour of Day | {features.get('hour_of_day', 'N/A')} |

## Data Sources
- INSAT-3D Satellite Imagery (MOSDAC/ISRO)
- OpenWeatherMap API
- Optical Flow Cloud Motion Vectors

## Methodology
1. **Optical Flow**: Farneback dense optical flow for cloud motion estimation
2. **Feature Engineering**: 30+ meteorological features extracted
3. **ML Model**: XGBoost classifier (trained on historical data)
4. **LLM Alert**: Groq Llama 3.1 for natural language generation
"""
    
    return report


if __name__ == "__main__":
    # Test alert generation
    prediction = {
        "thunderstorm_probability": 75.0,
        "risk_level": "HIGH",
        "risk_color": "red",
        "prediction": 1,
    }
    
    alert = generate_template_alert(prediction, "Delhi")
    print("✅ Template Alert:")
    print(alert)
