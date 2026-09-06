"""
utils/predictor.py
Thunderstorm and lightning probability model.

Two things went wrong in the original version and both are fixed here:

1. FEATURE CONTRACT. The old code built its feature vector in alphabetical
   order at inference but assigned feature names in a different hand-written
   order at training, and saved a model with no feature names at all. XGBoost
   silently accepted any column order, so the wrong numbers went into the wrong
   trees and nothing raised. Now a FeatureContract is persisted with the model
   and every prediction is validated against it by NAME, not by position.

2. PROVENANCE. The old model was trained on ``np.random.randn`` - Gaussian
   noise with no relationship to any observation - while inference fed it real
   values like 1013 hPa and 250 K. Every real sample fell off the end of every
   split, so the output was a near-constant number dressed up as a forecast.
   A model now records how it was trained, and anything trained on synthetic
   data is flagged ``synthetic`` so the UI can say so in plain language
   instead of implying a skill it does not have.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

import config
from utils import metrics as vmetrics

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:  # pragma: no cover
    HAS_XGB = False
    from sklearn.ensemble import GradientBoostingClassifier


class FeatureContractError(ValueError):
    """Raised when inference features do not match the trained contract."""


# --------------------------------------------------------------------------
# Feature contract
# --------------------------------------------------------------------------

@dataclass
class FeatureContract:
    """
    The binding agreement between training and inference.

    Holds the exact ordered feature names the model was fitted on, plus the
    training-time distribution of each feature so that out-of-range inputs can
    be detected rather than silently extrapolated.
    """

    names: List[str]
    means: List[float] = field(default_factory=list)
    stds: List[float] = field(default_factory=list)
    mins: List[float] = field(default_factory=list)
    maxs: List[float] = field(default_factory=list)

    @classmethod
    def from_matrix(cls, X: np.ndarray, names: Sequence[str]) -> "FeatureContract":
        X = np.asarray(X, dtype=float)
        if X.shape[1] != len(names):
            raise FeatureContractError(
                f"Cannot build contract: matrix has {X.shape[1]} columns but "
                f"{len(names)} names were supplied."
            )
        return cls(
            names=list(names),
            means=np.nanmean(X, axis=0).tolist(),
            stds=np.nanstd(X, axis=0).tolist(),
            mins=np.nanmin(X, axis=0).tolist(),
            maxs=np.nanmax(X, axis=0).tolist(),
        )

    def align(self, features: Dict[str, float]) -> np.ndarray:
        """
        Reorder a feature dictionary into the exact training column order.

        This is the function that makes column-order bugs impossible: features
        are looked up BY NAME, so the caller can build them in any order.

        Raises:
            FeatureContractError: if any contracted feature is missing.
        """
        missing = [n for n in self.names if n not in features]
        if missing:
            raise FeatureContractError(
                f"{len(missing)} feature(s) required by the model are missing "
                f"from the input: {missing[:8]}"
                + (" ..." if len(missing) > 8 else "")
            )

        extra = [k for k in features if k not in self.names]
        if extra:
            warnings.warn(
                f"Ignoring {len(extra)} feature(s) not in the model contract: "
                f"{extra[:8]}",
                stacklevel=2,
            )

        return np.array([float(features[n]) for n in self.names], dtype=np.float32)

    def out_of_range(self, vector: np.ndarray, n_sigma: float = 6.0) -> List[Dict]:
        """
        Report features that sit far outside the training distribution.

        This is the check that would have caught the original bug on day one:
        feeding pressure=1013 to a model trained on N(0,1) lights up here.
        """
        if not self.means or not self.stds:
            return []

        flagged = []
        for i, name in enumerate(self.names):
            value = float(vector[i])
            mean, std = self.means[i], self.stds[i]
            lo, hi = self.mins[i], self.maxs[i]
            if std > 1e-9:
                z = abs(value - mean) / std
                if z > n_sigma:
                    flagged.append({
                        "feature": name,
                        "value": value,
                        "z_score": z,
                        "training_range": (lo, hi),
                    })
        return flagged

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "FeatureContract":
        return cls(
            names=list(d.get("names", d.get("feature_names", []))),
            means=list(d.get("means", [])),
            stds=list(d.get("stds", [])),
            mins=list(d.get("mins", [])),
            maxs=list(d.get("maxs", [])),
        )

    def __len__(self) -> int:
        return len(self.names)


# --------------------------------------------------------------------------
# Model card
# --------------------------------------------------------------------------

@dataclass
class ModelCard:
    """
    Honest provenance for a trained model.

    ``training_data`` is the field that matters. 'synthetic' means the model has
    learned nothing about the atmosphere and its output must never be presented
    as a forecast.
    """

    training_data: str = "synthetic"        # synthetic | observed | mixed
    n_samples: int = 0
    n_features: int = 0
    trained_at: str = ""
    split_strategy: str = "none"            # none | random | temporal
    label_definition: str = ""
    data_sources: List[str] = field(default_factory=list)
    validation: Dict = field(default_factory=dict)
    notes: str = ""

    @property
    def is_demonstration_only(self) -> bool:
        """True when the model must be labelled as a demo, not a forecast."""
        return self.training_data != "observed"

    @property
    def banner(self) -> str:
        """One-line status a UI can show without further interpretation."""
        if self.training_data == "synthetic":
            return (
                "DEMONSTRATION MODE - this model is fitted to synthetic data. "
                "The probability shown exercises the pipeline; it is not a "
                "meteorological forecast and carries no skill."
            )
        if self.training_data == "mixed":
            return (
                "PARTIALLY TRAINED - fitted to a mixture of observed and "
                "synthetic samples. Treat outputs as provisional."
            )
        return (
            "OPERATIONAL - fitted to observed data with held-out temporal "
            "validation. See the verification panel for measured skill."
        )

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ModelCard":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# --------------------------------------------------------------------------
# Predictor
# --------------------------------------------------------------------------

class ThunderstormPredictor:
    """
    Gradient-boosted classifier for thunderstorm / lightning probability.

    Accepts features as a DICTIONARY at inference. Positional arrays are still
    accepted for batch scoring, but only when they are accompanied by names.
    """

    def __init__(self) -> None:
        self.model = None
        self.contract: Optional[FeatureContract] = None
        self.card = ModelCard()
        self.is_trained = False

    @property
    def feature_names(self) -> List[str]:
        return list(self.contract.names) if self.contract else []

    # -- training ----------------------------------------------------------

    def train(self,
              X: np.ndarray,
              y: np.ndarray,
              feature_names: Sequence[str],
              training_data: str = "synthetic",
              split_strategy: str = "temporal",
              timestamps: Optional[Sequence] = None,
              test_fraction: float = 0.25,
              n_estimators: int = 300,
              max_depth: int = 5,
              learning_rate: float = 0.05,
              label_definition: str = "",
              data_sources: Optional[List[str]] = None,
              baseline_prob: Optional[Sequence[float]] = None) -> Dict:
        """
        Fit the model with a held-out evaluation split.

        Args:
            X: feature matrix, shape (n_samples, n_features).
            y: binary labels.
            feature_names: names for the columns of X, in column order.
            training_data: 'synthetic', 'observed' or 'mixed' - recorded on
                the model card and surfaced in the UI.
            split_strategy: 'temporal' holds out the LAST portion in time,
                which is the only defensible split for a forecasting problem.
                'random' is available but leaks information across storms.
            timestamps: sample times, required for a temporal split to be
                meaningful. Falls back to array order if omitted.
            baseline_prob: optional competing forecast on the SAME test rows,
                so skill can be reported relative to a baseline.
        """
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y).astype(int).ravel()

        if X.shape[0] != y.shape[0]:
            raise ValueError(
                f"X has {X.shape[0]} rows but y has {y.shape[0]} labels."
            )
        if X.shape[1] != len(feature_names):
            raise FeatureContractError(
                f"X has {X.shape[1]} columns but {len(feature_names)} feature "
                "names were given. These must match exactly."
            )

        # -- split ---------------------------------------------------------
        n = X.shape[0]
        idx = np.arange(n)

        if split_strategy == "temporal":
            if timestamps is not None:
                idx = np.argsort(np.asarray(timestamps))
            cut = int(n * (1 - test_fraction))
            train_idx, test_idx = idx[:cut], idx[cut:]
        elif split_strategy == "random":
            rng = np.random.default_rng(42)
            rng.shuffle(idx)
            cut = int(n * (1 - test_fraction))
            train_idx, test_idx = idx[:cut], idx[cut:]
        else:
            train_idx, test_idx = idx, idx[:0]

        X_train, y_train = X[train_idx], y[train_idx]
        X_test, y_test = X[test_idx], y[test_idx]

        # -- class imbalance ----------------------------------------------
        # Thunderstorms are rare. Without this the model learns to say "no".
        n_pos = int(np.sum(y_train == 1))
        n_neg = int(np.sum(y_train == 0))
        scale_pos_weight = (n_neg / n_pos) if n_pos > 0 else 1.0

        # -- fit -----------------------------------------------------------
        if HAS_XGB:
            self.model = xgb.XGBClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=5,
                tree_method="hist",       # CPU-optimised
                eval_metric="aucpr",      # precision-recall: right for rare events
                scale_pos_weight=scale_pos_weight,
                random_state=42,
                # NOTE: use_label_encoder was removed in XGBoost 2.0.
                # Passing it raises on modern versions, so it is gone.
            )
            self.model.fit(X_train, y_train)
        else:  # pragma: no cover - fallback path
            self.model = GradientBoostingClassifier(
                n_estimators=n_estimators,
                max_depth=max_depth,
                learning_rate=learning_rate,
                random_state=42,
            )
            self.model.fit(X_train, y_train)

        self.contract = FeatureContract.from_matrix(X_train, feature_names)
        self.is_trained = True

        # -- verification --------------------------------------------------
        if len(test_idx) > 10 and len(np.unique(y_test)) > 1:
            test_prob = self.model.predict_proba(X_test)[:, 1]
            validation = vmetrics.full_report(
                y_test, test_prob, baseline_prob=baseline_prob
            )
            validation["n_test"] = int(len(test_idx))
        else:
            validation = {
                "warning": "Test split too small or single-class; "
                           "no verification metrics computed."
            }

        self.card = ModelCard(
            training_data=training_data,
            n_samples=int(n),
            n_features=int(X.shape[1]),
            trained_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            split_strategy=split_strategy,
            label_definition=label_definition,
            data_sources=data_sources or [],
            validation=validation,
        )

        importance = dict(sorted(
            zip(feature_names, self.model.feature_importances_.tolist()),
            key=lambda kv: kv[1],
            reverse=True,
        ))

        return {
            "n_train": int(len(train_idx)),
            "n_test": int(len(test_idx)),
            "positive_rate": float(np.mean(y)),
            "scale_pos_weight": float(scale_pos_weight),
            "feature_importance": importance,
            "validation": validation,
            "card": self.card.to_dict(),
        }

    # -- inference ---------------------------------------------------------

    def predict_proba(self, features: Dict[str, float]) -> float:
        """
        Probability of a thunderstorm, 0-100, from a NAMED feature mapping.

        Features are aligned by name against the trained contract, so the
        caller's ordering is irrelevant.
        """
        self._require_trained()
        vector = self.contract.align(features)
        proba = self.model.predict_proba(vector.reshape(1, -1))[0, 1]
        return float(proba * 100.0)

    def predict_batch(self,
                      X: np.ndarray,
                      feature_names: Sequence[str]) -> np.ndarray:
        """Score a matrix, reordering columns to the contract by name."""
        self._require_trained()
        X = np.asarray(X, dtype=np.float32)
        if X.shape[1] != len(feature_names):
            raise FeatureContractError(
                f"X has {X.shape[1]} columns but {len(feature_names)} names."
            )
        lookup = {n: i for i, n in enumerate(feature_names)}
        missing = [n for n in self.contract.names if n not in lookup]
        if missing:
            raise FeatureContractError(
                f"Missing contracted features: {missing[:8]}"
            )
        order = [lookup[n] for n in self.contract.names]
        return self.model.predict_proba(X[:, order])[:, 1] * 100.0

    def predict_single(self, features: Dict[str, float]) -> Dict:
        """
        Full prediction record for one sample.

        Returns probability, risk band, the model card banner, and any
        out-of-distribution warnings - everything the UI needs to present the
        number honestly.
        """
        self._require_trained()
        vector = self.contract.align(features)
        proba = float(self.model.predict_proba(vector.reshape(1, -1))[0, 1] * 100.0)
        band = config.classify_risk(proba)
        drift = self.contract.out_of_range(vector)

        return {
            "thunderstorm_probability": proba,
            "risk_level": band.name,
            "risk_color": band.color,
            "risk_hex": band.hex,
            "prediction": int(proba >= 50.0),
            "model_card": self.card.to_dict(),
            "is_demonstration_only": self.card.is_demonstration_only,
            "banner": self.card.banner,
            "out_of_distribution": drift,
            "trustworthy": (not self.card.is_demonstration_only) and not drift,
        }

    def feature_importance(self, top_n: int = 15) -> Dict[str, float]:
        """Top-N feature importances by name."""
        self._require_trained()
        pairs = sorted(
            zip(self.contract.names, self.model.feature_importances_.tolist()),
            key=lambda kv: kv[1],
            reverse=True,
        )
        return dict(pairs[:top_n])

    def _require_trained(self) -> None:
        if not self.is_trained or self.model is None:
            raise RuntimeError(
                "Model is not trained or loaded. Call train() or load_model()."
            )
        if self.contract is None or not self.contract.names:
            raise FeatureContractError(
                "Model has no feature contract. It was saved by an older, "
                "unsafe version and cannot be used for inference. Retrain it."
            )

    # -- persistence -------------------------------------------------------

    def save_model(self, filepath=config.MODEL_PATH) -> None:
        """Persist the model together with its contract and card."""
        self._require_trained()
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if HAS_XGB:
            self.model.save_model(str(filepath))
        else:  # pragma: no cover
            import joblib
            joblib.dump(self.model, filepath)

        meta = {
            "schema_version": 2,
            "contract": self.contract.to_dict(),
            "card": self.card.to_dict(),
            # kept so old readers do not crash outright
            "feature_names": self.contract.names,
            "is_trained": True,
        }
        meta_path = filepath.with_name(filepath.stem + "_meta.json")
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def load_model(self, filepath=config.MODEL_PATH) -> "ThunderstormPredictor":
        """
        Load a model and its contract.

        A model saved without a contract (schema v1) is refused rather than
        loaded, because using one silently produces wrong numbers.
        """
        filepath = Path(filepath)
        meta_path = filepath.with_name(filepath.stem + "_meta.json")

        if not meta_path.exists():
            raise FeatureContractError(
                f"No metadata beside {filepath.name}. Refusing to load a model "
                "without a feature contract - it would score features in an "
                "arbitrary column order."
            )

        meta = json.loads(meta_path.read_text(encoding="utf-8"))

        if meta.get("schema_version", 1) < 2 or "contract" not in meta:
            raise FeatureContractError(
                f"{meta_path.name} uses the legacy v1 format, which stored only "
                "a name list and no training distribution. Models in that "
                "format were trained on synthetic noise with mismatched column "
                "order. Retrain with `python -m utils.predictor` to continue."
            )

        if HAS_XGB:
            self.model = xgb.XGBClassifier()
            self.model.load_model(str(filepath))
        else:  # pragma: no cover
            import joblib
            self.model = joblib.load(filepath)

        self.contract = FeatureContract.from_dict(meta["contract"])
        self.card = ModelCard.from_dict(meta.get("card", {}))
        self.is_trained = True

        n_model_features = getattr(self.model, "n_features_in_", len(self.contract))
        if n_model_features and n_model_features != len(self.contract):
            raise FeatureContractError(
                f"Model expects {n_model_features} features but the contract "
                f"lists {len(self.contract)}. The metadata does not match the "
                "model file."
            )
        return self


# --------------------------------------------------------------------------
# Demonstration training data
# --------------------------------------------------------------------------

def generate_demo_training_data(feature_names: Sequence[str],
                                n_samples: int = 4000,
                                random_state: int = 42
                                ) -> Tuple[np.ndarray, np.ndarray, List]:
    """
    Physically-plausible SYNTHETIC data for demonstration only.

    Unlike the original ``np.random.randn`` version, each feature is drawn on
    its own realistic scale (Kelvin, hPa, percent, pixels) so that a model
    fitted here at least sits in the same numerical space as real inference
    inputs. That removes the catastrophic distribution mismatch, but it does
    NOT make the model skilful: the labels are still generated from a formula,
    not observed from the atmosphere. The model card says so.
    """
    rng = np.random.default_rng(random_state)

    def draw(name: str) -> np.ndarray:
        if name.startswith("bt_") and "gradient" not in name:
            return rng.normal(265, 22, n_samples).clip(190, 315)
        if "cooling_rate" in name:
            return rng.normal(0.02, 0.18, n_samples)
        if "fraction" in name:
            return rng.beta(1.6, 6.0, n_samples)
        if "texture" in name or "gradient" in name or "laplacian" in name:
            return rng.gamma(2.0, 3.0, n_samples)
        if name == "cloud_count":
            return rng.poisson(6, n_samples).astype(float)
        if "cloud_area" in name:
            return rng.gamma(2.0, 450.0, n_samples)
        if name == "hour_of_day":
            return rng.integers(0, 24, n_samples).astype(float)
        if name == "month":
            return rng.integers(1, 13, n_samples).astype(float)
        if name.startswith("is_"):
            return rng.integers(0, 2, n_samples).astype(float)
        if name == "temperature":
            return rng.normal(30, 6, n_samples)
        if name == "humidity":
            return rng.normal(68, 16, n_samples).clip(5, 100)
        if name == "pressure":
            return rng.normal(1006, 7, n_samples)
        if name == "wind_speed":
            return rng.gamma(2.0, 2.2, n_samples)
        if name == "wind_deg":
            return rng.uniform(0, 360, n_samples)
        if name == "cloud_cover":
            return rng.uniform(0, 100, n_samples)
        if name == "visibility":
            return rng.normal(8, 3, n_samples).clip(0.2, 15)
        if "flow_magnitude" in name:
            return rng.gamma(2.0, 1.5, n_samples)
        if "flow_direction" in name:
            return rng.uniform(-180, 180, n_samples)
        if "convergence" in name:
            return rng.normal(0, 0.6, n_samples)
        if name.startswith("cape"):
            return rng.gamma(2.0, 700.0, n_samples)
        if name.startswith("cin"):
            return -rng.gamma(2.0, 40.0, n_samples)
        if "shear" in name:
            return rng.gamma(2.0, 5.0, n_samples)
        if "lightning" in name or "strike" in name:
            return rng.poisson(2.0, n_samples).astype(float)
        if "reflectivity" in name or name.startswith("dbz"):
            return rng.normal(28, 12, n_samples).clip(0, 70)
        if "echo_top" in name:
            return rng.gamma(2.0, 3.0, n_samples).clip(0, 18)
        if "vil" in name:
            return rng.gamma(1.8, 2.0, n_samples)
        if "precipitable" in name or name.startswith("pwat"):
            return rng.normal(45, 12, n_samples).clip(5, 80)
        if "lifted_index" in name:
            return rng.normal(-2, 4, n_samples)
        if "k_index" in name:
            return rng.normal(30, 8, n_samples)
        if "total_totals" in name:
            return rng.normal(45, 6, n_samples)
        return rng.normal(0, 1, n_samples)

    columns = {name: draw(name) for name in feature_names}
    X = np.column_stack([columns[n] for n in feature_names]).astype(np.float32)

    def col(name: str, default: float = 0.0) -> np.ndarray:
        return columns.get(name, np.full(n_samples, default))

    def z(a: np.ndarray) -> np.ndarray:
        return (a - a.mean()) / (a.std() + 1e-9)

    logit = (
        -2.0
        + 1.10 * z(-col("bt_min", 265.0))          # colder tops -> deeper convection
        + 0.90 * z(col("cold_cloud_fraction"))
        + 0.80 * z(col("cooling_rate_max"))
        + 0.60 * z(col("rapid_cooling_fraction"))
        + 0.55 * z(col("cape_j_kg", 1200.0))
        + 0.45 * z(col("convergence_max"))
        + 0.45 * z(col("max_reflectivity_dbz", 28.0))
        + 0.40 * z(col("lightning_strike_count", 2.0))
        + 0.35 * z(col("humidity", 68.0))
        + 0.30 * z(col("texture_mean"))
        + 0.30 * col("is_peak_hour")
        + 0.25 * col("is_monsoon")
        - 0.30 * z(col("pressure", 1006.0))
        + 0.25 * rng.normal(0, 1, n_samples)
    )

    prob = 1.0 / (1.0 + np.exp(-logit))
    y = (rng.random(n_samples) < prob).astype(int)

    timestamps = list(range(n_samples))
    return X, y, timestamps


def train_demo_model(feature_names: Optional[Sequence[str]] = None,
                     save: bool = True) -> ThunderstormPredictor:
    """
    Train and persist the demonstration model.

    Clearly marked ``synthetic`` on its model card so every surface that shows
    its output can say what it is.
    """
    if feature_names is None:
        from utils.features import FEATURE_NAMES
        feature_names = FEATURE_NAMES

    X, y, timestamps = generate_demo_training_data(feature_names)

    predictor = ThunderstormPredictor()
    result = predictor.train(
        X, y,
        feature_names=feature_names,
        training_data="synthetic",
        split_strategy="temporal",
        timestamps=timestamps,
        label_definition=(
            "SYNTHETIC: label drawn from a hand-specified logistic function of "
            "the features. Not observed. Carries no meteorological skill."
        ),
        data_sources=["synthetic generator (utils.predictor)"],
    )

    if save:
        predictor.save_model()

    v = result["validation"]
    print(f"Trained demo model on {result['n_train']} samples "
          f"({result['positive_rate']:.1%} positive).")
    if "contingency" in v:
        print(vmetrics.format_report(v))
    print("\n" + predictor.card.banner)
    return predictor


if __name__ == "__main__":
    train_demo_model()
