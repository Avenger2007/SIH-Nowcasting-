"""
app.py
Main Streamlit application for Thunderstorm & Lightning Nowcasting Dashboard.
SIH 2026 - PS Number: SIH26072
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

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A5F;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #555;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .alert-high {
        background: #ff4444;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }
    .alert-moderate {
        background: #ff8800;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }
    .alert-low {
        background: #ffcc00;
        color: black;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }
    .alert-minimal {
        background: #44bb44;
        color: white;
        padding: 1rem;
        border-radius: 8px;
        font-weight: bold;
    }
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
    }


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
                importance = dict(zip(
                    results["feature_names"],
                    results["predictor"].model.feature_importances_
                ))
                top_features = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True)[:10])
                
                fig = px.bar(
                    x=list(top_features.values()),
                    y=list(top_features.keys()),
                    orientation='h',
                    title="Top 10 Feature Importances"
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # Detailed report
        with st.expander("📄 View Detailed Report"):
            report = generate_detailed_report(
                results["prediction"],
                location,
                results["flow_features"],
                results["timestamps"]
            )
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
