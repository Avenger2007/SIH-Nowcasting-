"""
utils/predictor.py
XGBoost model for thunderstorm probability prediction.
Trains on engineered features from satellite imagery and weather data.
Runs on CPU, trains in minutes, inference in milliseconds.
"""

import numpy as np
import json
import os
from typing import Dict, List, Tuple, Optional

# Conditional import for XGBoost
try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False
    print("⚠️ XGBoost not installed. Using sklearn GradientBoosting as fallback.")
    from sklearn.ensemble import GradientBoostingClassifier


class ThunderstormPredictor:
    """
    XGBoost-based thunderstorm probability predictor.
    
    Predicts probability of thunderstorm occurrence in 0-6 hours
    based on satellite imagery features, weather data, and optical flow.
    """
    
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.is_trained = False
    
    def train(self, X: np.ndarray, y: np.ndarray, 
              feature_names: List[str] = None,
              n_estimators: int = 200,
              max_depth: int = 5,
              learning_rate: float = 0.1) -> Dict:
        """
        Train the XGBoost model.
        
        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,) - 1 if thunderstorm occurred, 0 otherwise
            feature_names: List of feature names
            n_estimators: Number of trees
            max_depth: Maximum tree depth
            learning_rate: Learning rate
        
        Returns:
            Training metrics dictionary
        """
        self.feature_names = feature_names or [f"f{i}" for i in range(X.shape[1])]
        
        if HAS_XGB:
            self.model = xgb.XGBClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                tree_method='hist',  # CPU-optimized
                eval_metric='logloss',
                use_label_encoder=False,
                random_state=42
            )
        else:
            self.model = GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=42
            )
        
        # Train
        self.model.fit(X, y)
        self.is_trained = True
        
        # Training metrics
        train_accuracy = self.model.score(X, y)
        
        # Feature importance
        importance = dict(zip(
            self.feature_names,
            self.model.feature_importances_.tolist()
        ))
        # Sort by importance (descending)
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        
        metrics = {
            "train_accuracy": train_accuracy,
            "n_samples": X.shape[0],
            "n_features": X.shape[1],
            "feature_importance": importance,
        }
        
        print(f"✅ Model trained: accuracy={train_accuracy:.4f}, samples={X.shape[0]}")
        return metrics
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict thunderstorm probability.
        
        Args:
            X: Feature matrix (n_samples, n_features)
        
        Returns:
            predictions: Binary predictions (0 or 1)
            probabilities: Thunderstorm probability (0-100%)
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        predictions = self.model.predict(X)
        probabilities = self.model.predict_proba(X)[:, 1] * 100  # Scale to 0-100
        
        return predictions, probabilities
    
    def predict_single(self, feature_vector: np.ndarray) -> Dict:
        """
        Predict for a single feature vector.
        
        Returns:
            Dictionary with prediction results
        """
        if not self.is_trained:
            raise RuntimeError("Model not trained. Call train() first.")
        
        X = feature_vector.reshape(1, -1)
        pred, prob = self.predict(X)
        
        # Risk level
        risk_prob = prob[0]
        if risk_prob >= 70:
            risk_level = "HIGH"
            risk_color = "red"
        elif risk_prob >= 40:
            risk_level = "MODERATE"
            risk_color = "orange"
        elif risk_prob >= 20:
            risk_level = "LOW"
            risk_color = "yellow"
        else:
            risk_level = "MINIMAL"
            risk_color = "green"
        
        return {
            "thunderstorm_probability": float(risk_prob),
            "risk_level": risk_level,
            "risk_color": risk_color,
            "prediction": int(pred[0]),
        }
    
    def save_model(self, filepath: str = "models/xgb_model.json"):
        """Save model to disk."""
        if not self.is_trained:
            raise RuntimeError("Model not trained.")
        
        if HAS_XGB:
            self.model.save_model(filepath)
        else:
            import joblib
            joblib.dump(self.model, filepath)
        
        # Save metadata
        meta = {
            "feature_names": self.feature_names,
            "is_trained": self.is_trained,
        }
        meta_path = filepath.replace(".json", "_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        
        print(f"✅ Model saved to {filepath}")
    
    def load_model(self, filepath: str = "models/xgb_model.json"):
        """Load model from disk."""
        if HAS_XGB:
            self.model = xgb.XGBClassifier()
            self.model.load_model(filepath)
        else:
            import joblib
            self.model = joblib.load(filepath)
        
        # Load metadata
        meta_path = filepath.replace(".json", "_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, "r") as f:
                meta = json.load(f)
            self.feature_names = meta.get("feature_names", [])
        
        self.is_trained = True
        print(f"✅ Model loaded from {filepath}")


def generate_synthetic_training_data(n_samples: int = 1000, 
                                     n_features: int = 48,
                                     random_state: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic training data for demonstration.
    In production, use real labeled data from IMD/MOSDAC.
    
    The synthetic data simulates the relationship between
    satellite/weather features and thunderstorm occurrence.
    """
    np.random.seed(random_state)
    
    # Generate features
    X = np.random.randn(n_samples, n_features)
    
    # Create synthetic relationship (some features are more important)
    # Use min to avoid index out of range if n_features < 30
    n_rel = min(30, n_features)
    
    # Thunderstorm probability based on feature combinations
    logit = (
        -1.5 +  # baseline (thunderstorms are relatively rare)
        0.8 * X[:, 0] +   # cooling rate
        0.6 * X[:, 1] +   # cold cloud fraction
        0.5 * X[:, 2] +   # rapid cooling
        0.4 * X[:, 5] +   # texture
        0.3 * X[:, 9] +   # cloud count
        0.3 * X[:, 13] +  # afternoon
        0.2 * X[:, 17] +  # humidity
        0.2 * X[:, 23] +  # convergence
        0.1 * np.random.randn(n_samples)  # noise
    )
    
    # Convert to probability
    prob = 1 / (1 + np.exp(-logit))
    
    # Generate labels
    y = (np.random.random(n_samples) < prob).astype(int)
    
    return X, y


def train_and_save_model(n_features: int = 48):
    """Train model on synthetic data and save."""
    print("🔄 Generating synthetic training data...")
    X, y = generate_synthetic_training_data(n_samples=2000, n_features=n_features)
    
    feature_names = [
        "bt_mean", "bt_std", "bt_min", "bt_max",
        "bt_gradient_mean", "bt_gradient_std",
        "cooling_rate_mean", "cooling_rate_max", "cooling_rate_min", "cooling_rate_std",
        "cold_cloud_fraction", "rapid_cooling_fraction",
        "texture_mean", "texture_std", "texture_max",
        "gradient_mean", "gradient_std", "gradient_max",
        "laplacian_mean", "laplacian_std",
        "cloud_count", "max_cloud_area", "mean_cloud_area",
        "total_cloud_fraction", "cloud_area_std",
        "hour_of_day", "month", "is_afternoon", "is_evening", "is_night",
        "is_monsoon", "is_peak_hour",
        "temperature", "humidity", "pressure",
        "wind_speed", "wind_deg", "cloud_cover", "visibility",
        "flow_magnitude_mean", "flow_magnitude_std", "flow_magnitude_max",
        "flow_direction_mean", "flow_direction_std",
        "convergence_mean", "convergence_max", "convergence_min", "convergence_std",
    ]
    
    # Ensure feature_names matches X.shape[1]
    feature_names = feature_names[:X.shape[1]]
    
    predictor = ThunderstormPredictor()
    metrics = predictor.train(X, y, feature_names=feature_names)
    
    # Save
    os.makedirs("models", exist_ok=True)
    predictor.save_model("models/xgb_model.json")
    
    print(f"\n📊 Training Metrics:")
    print(f"   Accuracy: {metrics['train_accuracy']:.4f}")
    print(f"   Samples: {metrics['n_samples']}")
    print(f"   Features: {metrics['n_features']}")
    print(f"\n🔝 Top 5 Important Features:")
    for i, (name, imp) in enumerate(list(metrics['feature_importance'].items())[:5]):
        print(f"   {i+1}. {name}: {imp:.4f}")
    
    return predictor


if __name__ == "__main__":
    train_and_save_model()
