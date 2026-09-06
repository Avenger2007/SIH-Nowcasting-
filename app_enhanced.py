"""
app_enhanced.py
Enhanced Streamlit Dashboard for Thunderstorm & Lightning Nowcasting.
SIH 2026 - PS Number: SIH26072

New features: Folium map, satellite animation, hourly forecast chart,
download report, dark/light theme toggle, mobile-responsive layout.
"""

import streamlit as st
import cv2
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
import sys
import base64
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.satellite import generate_sample_satellite_images, fetch_openweather_data
from utils.optical_flow import compute_optical_flow, extract_flow_features, visualize_flow
from utils.features import build_feature_vector
from utils.predictor import ThunderstormPredictor, train_and_save_model
from utils.llm_alert import generate_alert, generate_template_alert, generate_detailed_report

# Page configuration
st.set_page_config(
    page_title="Thunderstorm Nowcasting | SIH 2026",
    page_icon="⛈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Theme toggle (in sidebar)
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# Custom CSS based on theme
if st.session_state.theme == 'dark':
    bg_color = "#1a1a2e"
    card_color = "#16213e"
    text_color = "#eaeaea"
    accent_color = "#e94560"
else:
    bg_color = "#f5f7fa"
    card_color = "#ffffff"
    text_color = "#1E3A5F"
    accent_color = "#667eea"

st.markdown(f"""
<style>
    .main-header {{
        font-size: 2.5rem;
        font-weight: bold;
        color: {text_color};
        text-align: center;
        margin-bottom: 0.5rem;
    }}
    .sub-header {{
        font-size: 1.2rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }}
    .metric-card {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }}
    .alert-high {{
        background: #ff4444;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }}
    .alert-moderate {{
        background: #ff8800;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }}
    .alert-low {{
        background: #ffcc00;
        color: black;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }}
    .alert-minimal {{
        background: #44bb44;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }}
    /* Mobile responsive */
    @media (max-width: 768px) {{
        .main-header {{ font-size: 1.5rem; }}
        .sub-header {{ font-size: 0.9rem; }}
    }}
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if 'images_generated' not in st.session_state:
        st.session_state.images_generated = False
    if 'image_paths' not in st.session_state:
        st.session_state.image_paths = []
    if 'timestamps' not in st.session_state:
        st.session_state.timestamps = []
    if 'images' not in st.session_state:
        st.session_state.images = []
    if 'predictor' not in st.session_state:
        st.session_state.predictor = None
    if 'prediction_result' not in st.session_state:
        st.session_state.prediction_result = None


def load_model(feature_names=None):
    """Load or train the XGBoost model."""
    predictor = ThunderstormPredictor()
    
    model_path = "models/xgb_model.json"
    if os.path.exists(model_path):
        try:
            predictor.load_model(model_path)
            return predictor
        except Exception as e:
            st.warning(f"Could not load model: {e}. Training new model...")
    
    # Train new model
    with st.spinner("Training XGBoost model..."):
        n_features = len(feature_names) if feature_names else 48
        predictor = train_and_save_model(n_features=n_features)
    
    return predictor


def run_prediction(location, api_key_weather=None):
    """Run the full prediction pipeline."""
    
    # Step 1: Generate/load satellite images
    with st.spinner("Fetching satellite imagery..."):
        image_paths, timestamps = generate_sample_satellite_images(count=6)
        images = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in image_paths]
    
    # Step 2: Compute optical flow
    with st.spinner("Computing cloud motion vectors..."):
        flow = compute_optical_flow(images[-2], images[-1])
        flow_features = extract_flow_features(flow, images[-1])
    
    # Step 3: Fetch weather data (optional)
    weather_data = None
    if api_key_weather and api_key_weather != "***":
        # Default to Delhi coordinates
        lat, lon = 28.6139, 77.2090
        weather_data = fetch_openweather_data(lat, lon, api_key_weather)
    
    # Step 4: Build feature vector
    with st.spinner("Engineering features..."):
        feature_vector, feature_names = build_feature_vector(
            images[-1], images[-2], timestamps, weather_data, flow_features
        )
    
    # Step 5: Load model and predict
    with st.spinner("Running ML prediction..."):
        predictor = load_model(feature_names=feature_names)
        prediction = predictor.predict_single(feature_vector)
    
    # Step 6: Generate alert
    alert = generate_template_alert(prediction, location, weather_data)
    
    # Step 7: Generate hourly forecast (simulated decay)
    base_prob = prediction['thunderstorm_probability']
    hourly_probs = []
    for h in range(7):
        # Probability peaks at 2-3 hours then decays
        if h == 0:
            hourly_probs.append(base_prob * 0.3)
        elif h <= 3:
            hourly_probs.append(base_prob * (0.5 + 0.1 * h))
        else:
            hourly_probs.append(max(5, base_prob * (1.2 - 0.15 * h)))
    
    return {
        "prediction": prediction,
        "alert": alert,
        "images": images,
        "image_paths": image_paths,
        "timestamps": timestamps,
        "flow": flow,
        "flow_features": flow_features,
        "feature_vector": feature_vector,
        "feature_names": feature_names,
        "weather_data": weather_data,
        "hourly_probs": hourly_probs,
        "predictor": predictor,
    }


def get_location_coordinates(location):
    """Get lat/lon for Indian cities."""
    coords = {
        "Delhi": (28.6139, 77.2090),
        "Mumbai": (19.0760, 72.8777),
        "Kolkata": (22.5726, 88.3639),
        "Chennai": (13.0827, 80.2707),
        "Bangalore": (12.9716, 77.5946),
        "Hyderabad": (17.3850, 78.4867),
        "Pune": (18.5204, 73.8567),
        "Ahmedabad": (23.0225, 72.5714),
        "Jaipur": (26.9124, 75.7873),
        "Lucknow": (26.8467, 80.9462),
        "Patna": (25.6093, 85.1376),
        "Bhopal": (23.2599, 77.4126),
        "Guwahati": (26.1445, 91.7362),
        "Imphal": (24.8170, 93.9368),
        "Shillong": (25.5788, 91.8933),
        "Aizawl": (23.7271, 92.7176),
        "Kohima": (25.6751, 94.1086),
        "Gangtok": (27.3389, 88.6065),
        "Agartala": (23.8315, 91.2868),
        "Ranchi": (23.3441, 85.3096),
        "Bhubaneswar": (20.2961, 85.8245),
        "Raipur": (21.2514, 81.6296),
        "Dehradun": (30.3165, 78.0322),
    }
    return coords.get(location, (28.6139, 77.2090))


def create_folium_map(location, lat, lon, risk_level):
    """Create Folium interactive map with prediction marker."""
    try:
        import folium
        from folium import plugins
        
        # Color based on risk
        color_map = {
            "HIGH": "red",
            "MODERATE": "orange",
            "LOW": "blue",
            "MINIMAL": "green"
        }
        color = color_map.get(risk_level, "blue")
        
        m = folium.Map(location=[lat, lon], zoom_start=8)
        
        # Add marker
        folium.CircleMarker(
            location=[lat, lon],
            radius=15,
            popup=f"{location}: {risk_level} risk",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.6,
        ).add_to(m)
        
        # Add 50km radius circle
        folium.Circle(
            location=[lat, lon],
            radius=50000,
            popup="Warning Zone (50km)",
            color=color,
            fill=True,
            fillOpacity=0.1,
        ).add_to(m)
        
        return m
    except ImportError:
        return None


def create_hourly_forecast_chart(hourly_probs):
    """Create hourly forecast probability chart."""
    hours = [f"{h} hr" for h in range(7)]
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=hours,
        y=hourly_probs,
        mode='lines+markers',
        name='Thunderstorm Probability',
        line=dict(color='#e94560', width=3),
        marker=dict(size=10),
        fill='tozeroy',
        fillcolor='rgba(233, 69, 96, 0.1)',
    ))
    
    fig.add_hline(y=70, line_dash="dash", line_color="red", 
                  annotation_text="HIGH threshold")
    fig.add_hline(y=40, line_dash="dash", line_color="orange",
                  annotation_text="MODERATE threshold")
    
    fig.update_layout(
        title="Hourly Thunderstorm Forecast (0-6 hours)",
        xaxis_title="Lead Time",
        yaxis_title="Probability (%)",
        yaxis_range=[0, 100],
        height=300,
    )
    
    return fig


def create_feature_importance_chart(predictor, feature_names):
    """Create feature importance bar chart."""
    importance = dict(zip(
        feature_names,
        predictor.model.feature_importances_
    ))
    top_features = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])
    
    fig = px.bar(
        x=list(top_features.values()),
        y=list(top_features.keys()),
        orientation='h',
        title="Top 10 Feature Importances",
        color=list(top_features.values()),
        color_continuous_scale='Viridis',
    )
    fig.update_layout(height=300, showlegend=False)
    
    return fig


def get_download_link(content, filename, text):
    """Generate a download link for a file."""
    b64 = base64.b64encode(content.encode()).decode()
    href = f'<a href="data:file/txt;base64,{b64}" download="{filename}" class="download-link">{text}</a>'
    return href


def main():
    """Main application."""
    
    # Header
    st.markdown('<div class="main-header">⛈️ Thunderstorm & Lightning Nowcasting</div>', 
                unsafe_allow_html=True)
    st.markdown('<div class="sub-header">AI/ML-Based 0-6 Hour Nowcasting | SIH 2026 | PS: SIH26072</div>', 
                unsafe_allow_html=True)
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        location = st.selectbox(
            "Select Location",
            ["Delhi", "Mumbai", "Kolkata", "Chennai", "Bangalore", "Hyderabad", 
             "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Patna", "Bhopal",
             "Guwahati", "Imphal", "Shillong", "Aizawl", "Kohima", "Gangtok",
             "Agartala", "Ranchi", "Bhubaneswar", "Raipur", "Dehradun"]
        )
        
        st.markdown("---")
        
        # API Keys
        st.subheader("API Keys (Optional)")
        api_key_weather = st.text_input("OpenWeatherMap API Key", type="password")
        
        st.markdown("---")
        
        # Theme toggle
        st.subheader("🎨 Theme")
        theme = st.radio("Choose Theme", ["Light", "Dark"], index=0 if st.session_state.theme == 'light' else 1)
        if theme == "Dark" and st.session_state.theme != 'dark':
            st.session_state.theme = 'dark'
            st.rerun()
        elif theme == "Light" and st.session_state.theme != 'light':
            st.session_state.theme = 'light'
            st.rerun()
        
        st.markdown("---")
        
        # Run prediction button
        run_clicked = st.button("🚀 Run Nowcasting", type="primary", use_container_width=True)
        
        st.markdown("---")
        
        # Info
        st.info("""
        **How it works:**
        1. Fetches satellite imagery
        2. Computes optical flow (cloud motion)
        3. Extracts 30+ meteorological features
        4. XGBoost predicts thunderstorm probability
        5. Generates natural language alert
        """)
    
    # Main content
    if run_clicked:
        with st.spinner("Running full nowcasting pipeline..."):
            results = run_prediction(location, api_key_weather)
        
        # Display results
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("📊 Prediction Results")
            
            # Risk level alert
            risk_level = results["prediction"]["risk_level"]
            alert_class = f"alert-{risk_level.lower()}"
            st.markdown(f'<div class="{alert_class}">{results["alert"]}</div>', 
                       unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Probability gauge
            prob = results["prediction"]["thunderstorm_probability"]
            
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=prob,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Thunderstorm Probability (%)"},
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 20], 'color': "lightgreen"},
                        {'range': [20, 40], 'color': "yellow"},
                        {'range': [40, 70], 'color': "orange"},
                        {'range': [70, 100], 'color': "red"},
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': prob
                    }
                }
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📈 Key Metrics")
            
            # Metrics
            st.metric("Risk Level", risk_level)
            st.metric("Probability", f"{prob:.1f}%")
            st.metric("Lead Time", "0-6 hours")
            st.metric("Cloud Count", results["flow_features"].get("cloud_count", "N/A"))
            
            st.markdown("---")
            
            # Flow features
            st.subheader("🌬️ Cloud Motion")
            st.write(f"Avg Speed: {results['flow_features']['flow_magnitude_mean']:.2f} px/frame")
            st.write(f"Convergence: {results['flow_features']['convergence_mean']:.4f}")
        
        st.markdown("---")
        
        # Hourly forecast chart
        st.subheader("⏰ Hourly Forecast (0-6 hours)")
        hourly_chart = create_hourly_forecast_chart(results["hourly_probs"])
        st.plotly_chart(hourly_chart, use_container_width=True)
        
        st.markdown("---")
        
        # Satellite imagery display
        st.subheader("🛰️ Satellite Imagery Analysis")
        
        img_col1, img_col2, img_col3 = st.columns(3)
        
        with img_col1:
            st.image(results["image_paths"][-1], caption="Latest IR Image", use_column_width=True)
        
        with img_col2:
            # Optical flow visualization
            flow_vis = visualize_flow(results["flow"], results["images"][-1])
            st.image(flow_vis, caption="Optical Flow (Cloud Motion)", use_column_width=True)
        
        with img_col3:
            # Feature importance chart
            if results.get("predictor") and results["predictor"].is_trained:
                fig_chart = create_feature_importance_chart(results["predictor"], results["feature_names"])
                st.plotly_chart(fig_chart, use_container_width=True)
        
        st.markdown("---")
        
        # Folium Map
        st.subheader("🗺️ Location Map")
        lat, lon = get_location_coordinates(location)
        folium_map = create_folium_map(location, lat, lon, risk_level)
        if folium_map:
            from streamlit_folium import st_folium
            st_folium(folium_map, width=700, height=400)
        else:
            st.info("Install folium and streamlit-folium for interactive map: `pip install folium streamlit-folium`")
            st.write(f"**{location}** — Lat: {lat}, Lon: {lon}")
        
        st.markdown("---")
        
        # Satellite image animation/slideshow
        st.subheader("🎞️ Satellite Image Sequence")
        image_index = st.selectbox(
            "Select Image",
            [f"Image {i+1} - {results['timestamps'][i].strftime('%H:%M UTC')}" for i in range(len(results["image_paths"]))],
            index=len(results["image_paths"]) - 1
        )
        idx = int(image_index.split(" ")[1]) - 1
        st.image(results["image_paths"][idx], caption=image_index, use_column_width=True)
        
        st.markdown("---")
        
        # Download report button
        st.subheader("📄 Download Report")
        report = generate_detailed_report(
            results["prediction"],
            location,
            results["flow_features"],
            results["timestamps"]
        )
        st.markdown(get_download_link(report, f"thunderstorm_report_{location}_{datetime.now().strftime('%Y%m%d')}.md", "📥 Download Report (Markdown)"), unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Detailed report expander
        with st.expander("📋 View Detailed Report"):
            st.markdown(report)
    
    else:
        # Default display before running
        st.info("👈 Select a location and click 'Run Nowcasting' to start the prediction pipeline.")
        
        # Show architecture diagram
        st.subheader("🏗️ System Architecture")
        
        arch_col1, arch_col2, arch_col3 = st.columns(3)
        
        with arch_col1:
            st.info("""
            **Stage 1: Data Acquisition**
            - INSAT-3D Satellite IR Imagery
            - OpenWeatherMap API
            - Ground Observations
            """)
        
        with arch_col2:
            st.warning("""
            **Stage 2: AI Processing**
            - Optical Flow (Cloud Motion)
            - Feature Engineering (30+ features)
            - XGBoost Prediction
            """)
        
        with arch_col3:
            st.success("""
            **Stage 3: Alert Generation**
            - Natural Language Alert
            - Risk Classification
            - Public Dissemination
            """)
        
        st.markdown("---")
        
        # Problem statement info
        st.subheader("📋 Problem Statement Details")
        
        details_col1, details_col2 = st.columns(2)
        
        with details_col1:
            st.write("""
            **PS Number:** SIH26072  
            **Organization:** Ministry of Earth Sciences (MoES)  
            **Category:** Software  
            **Theme:** Disaster Management  
            **Ideas Submitted:** 0/500  
            **Deadline:** 30 September 2026
            """)
        
        with details_col2:
            st.write("""
            **Key Requirements:**
            - AI/ML-based nowcasting
            - 0-6 hour lead time
            - Thunderstorm & lightning prediction
            - Multi-source data fusion
            - Real-time capability
            """)


if __name__ == "__main__":
    main()
