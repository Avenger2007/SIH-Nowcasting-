"""
tests/test_pipeline.py
Pytest tests for the Thunderstorm Nowcasting pipeline.
"""

import os
import sys
import tempfile
import shutil

import numpy as np
import cv2
import pytest

# Add project root to path so utils can be imported
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

from utils.satellite import generate_sample_satellite_images
from utils.optical_flow import compute_optical_flow, extract_flow_features
from utils.features import build_feature_vector
from utils.predictor import ThunderstormPredictor, generate_synthetic_training_data
from utils.llm_alert import generate_template_alert


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_images(tmp_path):
    """Generate a small set of sample satellite images for testing."""
    images, timestamps = generate_sample_satellite_images(
        output_dir=str(tmp_path / "sample_images"), count=4
    )
    return images, timestamps


@pytest.fixture
def grayscale_pair():
    """Create two simple grayscale images for optical flow testing."""
    np.random.seed(0)
    img1 = np.random.randint(100, 200, (64, 64), dtype=np.uint8)
    # Shift img1 slightly to create img2 (simulate cloud motion)
    img2 = np.roll(img1, 2, axis=1)
    img2 = np.roll(img2, 1, axis=0)
    return img1, img2


@pytest.fixture
def trained_predictor():
    """Train a small model for prediction tests."""
    X, y = generate_synthetic_training_data(n_samples=200, n_features=48)
    predictor = ThunderstormPredictor()
    predictor.train(X, y, n_estimators=20, max_depth=3)
    return predictor


# ---------------------------------------------------------------------------
# 1. Satellite image generation
# ---------------------------------------------------------------------------

def test_satellite_generation(tmp_path):
    """Test that sample satellite images are generated correctly."""
    output_dir = str(tmp_path / "test_satellite")
    images, timestamps = generate_sample_satellite_images(
        output_dir=output_dir, count=4
    )

    # Correct number of images and timestamps
    assert len(images) == 4
    assert len(timestamps) == 4

    # Files exist on disk
    for path in images:
        assert os.path.isfile(path), f"Image file not found: {path}"

    # Images are valid and loadable
    for path in images:
        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        assert img is not None, f"Could not load image: {path}"
        assert img.shape == (256, 256), f"Unexpected shape: {img.shape}"
        assert img.dtype == np.uint8


# ---------------------------------------------------------------------------
# 2. Optical flow
# ---------------------------------------------------------------------------

def test_optical_flow(grayscale_pair):
    """Test optical flow computation and feature extraction."""
    img1, img2 = grayscale_pair

    flow = compute_optical_flow(img1, img2)

    # Flow shape: (H, W, 2)
    assert flow.shape == (64, 64, 2)
    assert flow.dtype == np.float32

    # Flow should not be all zero (images are different)
    assert np.any(flow != 0)

    # Extract features
    features = extract_flow_features(flow, img2)
    assert isinstance(features, dict)
    assert "flow_magnitude_mean" in features
    assert "flow_magnitude_max" in features
    assert "convergence_mean" in features

    # Magnitude stats should be non-negative
    assert features["flow_magnitude_mean"] >= 0
    assert features["flow_magnitude_max"] >= 0


# ---------------------------------------------------------------------------
# 3. Feature engineering
# ---------------------------------------------------------------------------

def test_feature_engineering(grayscale_pair):
    """Test that build_feature_vector returns a consistent numeric vector."""
    img1, img2 = grayscale_pair
    from datetime import datetime
    timestamps = [datetime(2026, 7, 15, 14, 30)]

    feature_vector, feature_names = build_feature_vector(
        img2, img1, timestamps
    )

    # Vector is 1-D float32
    assert isinstance(feature_vector, np.ndarray)
    assert feature_vector.ndim == 1
    assert feature_vector.dtype == np.float32

    # No NaN or Inf values
    assert not np.any(np.isnan(feature_vector))
    assert not np.any(np.isinf(feature_vector))

    # Feature names match vector length
    assert len(feature_names) == feature_vector.shape[0]

    # Expected number of features (cooling + texture + cloud + temporal + weather + flow)
    assert len(feature_names) >= 30


# ---------------------------------------------------------------------------
# 4. Model training
# ---------------------------------------------------------------------------

def test_model_training():
    """Test that ThunderstormPredictor trains successfully."""
    X, y = generate_synthetic_training_data(n_samples=200, n_features=48)

    predictor = ThunderstormPredictor()
    metrics = predictor.train(X, y, n_estimators=20, max_depth=3)

    # Model is trained
    assert predictor.is_trained is True

    # Metrics contain expected keys
    assert "train_accuracy" in metrics
    assert "n_samples" in metrics
    assert "n_features" in metrics
    assert "feature_importance" in metrics

    # Accuracy is reasonable (above random for 2 classes)
    assert metrics["train_accuracy"] > 0.5
    assert metrics["n_samples"] == 200
    assert metrics["n_features"] == 48


# ---------------------------------------------------------------------------
# 5. Prediction
# ---------------------------------------------------------------------------

def test_prediction(trained_predictor):
    """Test prediction on a single sample."""
    X, _ = generate_synthetic_training_data(n_samples=5, n_features=48)

    predictions, probabilities = trained_predictor.predict(X)

    # Shapes
    assert predictions.shape == (5,)
    assert probabilities.shape == (5,)

    # Predictions are binary
    assert set(predictions.tolist()).issubset({0, 1})

    # Probabilities in [0, 100]
    assert np.all(probabilities >= 0)
    assert np.all(probabilities <= 100)

    # Single prediction
    result = trained_predictor.predict_single(X[0])
    assert "thunderstorm_probability" in result
    assert "risk_level" in result
    assert result["risk_level"] in {"HIGH", "MODERATE", "LOW", "MINIMAL"}


# ---------------------------------------------------------------------------
# 6. Alert generation
# ---------------------------------------------------------------------------

def test_alert_generation():
    """Test template-based alert generation for all risk levels."""
    for risk_level, expected_keyword in [
        ("HIGH", "ALERT"),
        ("MODERATE", "WATCH"),
        ("LOW", "ADVISORY"),
        ("MINIMAL", "UPDATE"),
    ]:
        prediction = {
            "thunderstorm_probability": 75.0,
            "risk_level": risk_level,
            "risk_color": "red",
            "prediction": 1,
        }
        alert = generate_template_alert(prediction, "Delhi")

        assert isinstance(alert, str)
        assert len(alert) > 0
        assert "Delhi" in alert
        assert expected_keyword in alert


# ---------------------------------------------------------------------------
# 7. Model save / load
# ---------------------------------------------------------------------------

def test_model_save_load(trained_predictor, tmp_path):
    """Test that a trained model can be saved and reloaded."""
    model_path = str(tmp_path / "test_model.json")

    # Save
    trained_predictor.save_model(model_path)
    assert os.path.isfile(model_path)

    # Load into a new predictor
    new_predictor = ThunderstormPredictor()
    new_predictor.load_model(model_path)

    assert new_predictor.is_trained is True
    assert new_predictor.feature_names == trained_predictor.feature_names

    # Predictions should match
    X, _ = generate_synthetic_training_data(n_samples=10, n_features=48)
    pred1, prob1 = trained_predictor.predict(X)
    pred2, prob2 = new_predictor.predict(X)

    np.testing.assert_array_equal(pred1, pred2)
    np.testing.assert_allclose(prob1, prob2, atol=1e-5)


# ---------------------------------------------------------------------------
# 8. End-to-end pipeline
# ---------------------------------------------------------------------------

def test_end_to_end_pipeline(tmp_path):
    """Run the full pipeline: images → flow → features → predict → alert."""
    from datetime import datetime

    # Step 1: Generate satellite images
    output_dir = str(tmp_path / "e2e_images")
    image_paths, timestamps = generate_sample_satellite_images(
        output_dir=output_dir, count=4
    )
    assert len(image_paths) == 4

    # Step 2: Load images as grayscale
    images = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in image_paths]
    assert all(img is not None for img in images)

    # Step 3: Compute optical flow between last two images
    flow = compute_optical_flow(images[-2], images[-1])
    assert flow.shape[:2] == images[-1].shape

    # Step 4: Extract flow features
    flow_features = extract_flow_features(flow, images[-1])
    assert isinstance(flow_features, dict)

    # Step 5: Build feature vector
    feature_vector, feature_names = build_feature_vector(
        images[-1], images[-2], timestamps, flow_features=flow_features
    )
    assert feature_vector.ndim == 1
    assert not np.any(np.isnan(feature_vector))

    # Step 6: Train a model (small, for speed)
    X, y = generate_synthetic_training_data(n_samples=200, n_features=len(feature_vector))
    predictor = ThunderstormPredictor()
    predictor.train(X, y, n_estimators=20, max_depth=3)
    assert predictor.is_trained

    # Step 7: Predict
    result = predictor.predict_single(feature_vector)
    assert "thunderstorm_probability" in result
    assert "risk_level" in result

    # Step 8: Generate alert
    alert = generate_template_alert(result, "Delhi")
    assert isinstance(alert, str)
    assert "Delhi" in alert
    assert len(alert) > 20