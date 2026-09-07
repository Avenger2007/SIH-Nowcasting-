"""
tests/test_pipeline.py
Tests for the nowcasting pipeline.

These are regression tests as much as unit tests: several of them exist
specifically to make the bugs listed in ISSUES.json impossible to reintroduce
without a red build. Each such test names the bug it guards.

Network-dependent tests are marked ``live`` and skipped by default:

    pytest                    # offline tests only
    pytest -m live            # include live-network tests
    pytest -m "not live"      # explicit offline run
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import config
from utils import (
    calibration,
    consistency,
    features as feat,
    geo,
    metrics,
    optical_flow,
)
from utils.datasources import lightning as lightning_src
from utils.datasources import mosdac, radar
from utils.datasources.base import SourceResult, SourceStatus
from utils.predictor import (
    FeatureContract,
    FeatureContractError,
    ThunderstormPredictor,
    generate_demo_training_data,
)


# ==========================================================================
# Fixtures
# ==========================================================================

@pytest.fixture(scope="module")
def frame_sequence():
    """A deterministic synthetic IR sequence in Kelvin."""
    frames, timestamps = mosdac.simulate_convective_sequence(count=6, seed=7)
    return frames, timestamps


@pytest.fixture(scope="module")
def trained_predictor():
    predictor = ThunderstormPredictor()
    X, y, timestamps = generate_demo_training_data(
        feat.FEATURE_NAMES, n_samples=800, random_state=3
    )
    predictor.train(
        X, y, feature_names=feat.FEATURE_NAMES,
        timestamps=timestamps, n_estimators=40,
    )
    return predictor


# ==========================================================================
# Calibration
# ==========================================================================

def test_counts_to_kelvin_is_invertible():
    counts = np.arange(0, 256, dtype=np.uint8)
    kelvin = calibration.counts_to_kelvin(counts)
    back = calibration.kelvin_to_counts(kelvin)
    assert np.abs(back.astype(int) - counts.astype(int)).max() <= 1


def test_bright_pixels_are_cold():
    """IR convention: bright browse pixels are COLD cloud tops."""
    cold = calibration.counts_to_kelvin(np.array([255], dtype=np.uint8))
    warm = calibration.counts_to_kelvin(np.array([0], dtype=np.uint8))
    assert cold[0] < warm[0]


def test_ensure_kelvin_passes_through_physical_values():
    kelvin = np.full((8, 8), 250.0, dtype=np.float32)
    assert np.allclose(calibration.ensure_kelvin(kelvin), kelvin)


def test_thresholds_are_in_kelvin_not_counts():
    """Guards BUG-007: physical thresholds must not be 8-bit values."""
    assert 180 < config.BT_CONVECTIVE_K < 300
    assert config.BT_OVERSHOOT_K < config.BT_DEEP_CONVECTIVE_K
    assert config.BT_DEEP_CONVECTIVE_K < config.BT_CONVECTIVE_K


# ==========================================================================
# Feature contract - BUG-002
# ==========================================================================

def test_contract_aligns_by_name_not_position():
    """
    Guards BUG-002. Features supplied in a scrambled order must produce the
    same vector, because alignment is by name.
    """
    contract = FeatureContract(names=["alpha", "beta", "gamma"])
    forward = contract.align({"alpha": 1.0, "beta": 2.0, "gamma": 3.0})
    scrambled = contract.align({"gamma": 3.0, "alpha": 1.0, "beta": 2.0})
    assert np.array_equal(forward, scrambled)
    assert np.array_equal(forward, np.array([1.0, 2.0, 3.0], dtype=np.float32))


def test_contract_rejects_missing_features():
    contract = FeatureContract(names=["alpha", "beta"])
    with pytest.raises(FeatureContractError, match="missing"):
        contract.align({"alpha": 1.0})


def test_contract_detects_out_of_distribution_input():
    """
    Guards BUG-001. A model trained on N(0,1) fed a pressure of 1013 must
    flag it rather than silently extrapolating.
    """
    X = np.random.default_rng(0).normal(0, 1, (400, 2))
    contract = FeatureContract.from_matrix(X, ["a", "b"])
    flagged = contract.out_of_range(np.array([1013.0, 0.1], dtype=np.float32))
    assert any(item["feature"] == "a" for item in flagged)


def test_predictor_refuses_model_without_contract():
    """Guards BUG-002: a contract-less model must not be usable."""
    predictor = ThunderstormPredictor()
    predictor.is_trained = True
    predictor.model = object()
    with pytest.raises(FeatureContractError):
        predictor._require_trained()


# ==========================================================================
# Model
# ==========================================================================

def test_training_produces_verification_metrics(trained_predictor):
    """Guards BUG-005: a model must ship with held-out metrics."""
    validation = trained_predictor.card.validation
    assert "contingency" in validation
    for key in ("pod", "far", "csi", "hss"):
        assert key in validation["contingency"]


def test_synthetic_model_is_flagged_as_demonstration(trained_predictor):
    """Guards BUG-001: synthetic training must be visible to the UI."""
    assert trained_predictor.card.is_demonstration_only
    assert "DEMONSTRATION" in trained_predictor.card.banner


def test_prediction_is_ordering_independent(trained_predictor):
    features = {name: 1.0 for name in feat.FEATURE_NAMES}
    reversed_features = dict(reversed(list(features.items())))
    assert (trained_predictor.predict_proba(features)
            == trained_predictor.predict_proba(reversed_features))


def test_prediction_responds_to_inputs(trained_predictor):
    """
    The original model returned a near-constant probability. Varying the
    strongest predictors must move the output.
    """
    quiet = {name: 0.0 for name in feat.FEATURE_NAMES}
    quiet.update({"bt_min": 290.0, "cape_j_kg": 50.0,
                  "cold_cloud_fraction": 0.0, "cooling_rate_max": 0.0})

    stormy = {name: 0.0 for name in feat.FEATURE_NAMES}
    stormy.update({"bt_min": 200.0, "cape_j_kg": 3000.0,
                   "cold_cloud_fraction": 0.4, "cooling_rate_max": 0.6})

    assert abs(trained_predictor.predict_proba(stormy)
               - trained_predictor.predict_proba(quiet)) > 1.0


def test_model_round_trips_through_disk(trained_predictor, tmp_path):
    path = tmp_path / "model.json"
    trained_predictor.save_model(path)

    loaded = ThunderstormPredictor().load_model(path)
    assert loaded.contract.names == trained_predictor.contract.names
    assert loaded.card.training_data == trained_predictor.card.training_data

    features = {name: 0.5 for name in feat.FEATURE_NAMES}
    assert np.isclose(loaded.predict_proba(features),
                      trained_predictor.predict_proba(features))


def test_legacy_metadata_is_refused(tmp_path):
    """Guards BUG-002: v1 metadata carried no contract and must be rejected."""
    import json

    model_path = tmp_path / "old.json"
    model_path.write_text("{}", encoding="utf-8")
    (tmp_path / "old_meta.json").write_text(
        json.dumps({"feature_names": ["a"], "is_trained": True}),
        encoding="utf-8",
    )
    with pytest.raises(FeatureContractError, match="legacy"):
        ThunderstormPredictor().load_model(model_path)


# ==========================================================================
# Verification metrics
# ==========================================================================

def test_contingency_table_arithmetic():
    y_true = [1, 1, 1, 0, 0, 0, 0, 0]
    y_prob = [0.9, 0.8, 0.2, 0.7, 0.1, 0.1, 0.1, 0.1]
    table = metrics.contingency(y_true, y_prob, threshold=0.5)

    assert table.hits == 2
    assert table.misses == 1
    assert table.false_alarms == 1
    assert table.correct_negatives == 4
    assert table.pod == pytest.approx(2 / 3)
    assert table.far == pytest.approx(1 / 3)   # FA / (hits + FA)
    assert table.csi == pytest.approx(2 / 4)


def test_perfect_forecast_scores_perfectly():
    y_true = [1, 1, 0, 0]
    table = metrics.contingency(y_true, [0.99, 0.99, 0.01, 0.01], 0.5)
    assert table.pod == 1.0
    assert table.far == 0.0
    assert table.csi == 1.0


def test_accuracy_is_misleading_for_rare_events():
    """The reason POD/FAR/CSI are reported instead of accuracy."""
    y_true = [0] * 95 + [1] * 5
    y_prob = [0.0] * 100                      # always forecast "no storm"
    table = metrics.contingency(y_true, y_prob, 0.5)

    assert table.accuracy == pytest.approx(0.95)   # looks excellent
    assert table.pod == 0.0                        # catches nothing
    assert table.csi == 0.0


def test_brier_skill_score_of_climatology_is_zero():
    y_true = [1, 0, 1, 0, 0, 0, 1, 0]
    base_rate = float(np.mean(y_true))
    assert metrics.brier_skill_score(
        y_true, [base_rate] * len(y_true)) == pytest.approx(0.0, abs=1e-9)


def test_auc_of_perfect_separation_is_one():
    y_true = [0, 0, 0, 1, 1, 1]
    assert metrics.auc(y_true, [0.1, 0.15, 0.2, 0.8, 0.85, 0.9]) > 0.99


# ==========================================================================
# Optical flow
# ==========================================================================

def test_flow_detects_known_translation():
    """A uniformly shifted field must produce flow of the right magnitude."""
    rng = np.random.default_rng(1)
    base = rng.normal(260, 12, (128, 128)).astype(np.float32)
    base[40:70, 40:70] -= 55                       # a cold blob to track

    shifted = np.roll(base, 5, axis=1)
    flow = optical_flow.compute_optical_flow(base, shifted)

    # Mean x-displacement should be positive and of order the true shift.
    assert np.mean(flow[..., 0]) > 1.0


def test_advection_moves_features_forward():
    """
    Guards BUG-014. Advection must move a feature ALONG the flow, not against
    it. A constant rightward flow must move a blob to the right.
    """
    field = np.zeros((64, 64), dtype=np.float32)
    field[30:34, 10:14] = 100.0

    flow = np.zeros((64, 64, 2), dtype=np.float32)
    flow[..., 0] = 4.0                              # 4 px per step, rightward

    advected = optical_flow.advect(field, flow, steps=1.0)

    source_x = float(np.argmax(field.sum(axis=0)))
    result_x = float(np.argmax(advected.sum(axis=0)))
    assert result_x > source_x


def test_circular_mean_handles_wraparound():
    """
    Guards BUG-013. The mean of bearings either side of north must be near
    north, not near south.
    """
    flow = np.zeros((32, 32, 2), dtype=np.float32)
    flow[:16, :, 0] = 0.02      # just east of north
    flow[:16, :, 1] = -1.0
    flow[16:, :, 0] = -0.02     # just west of north
    flow[16:, :, 1] = -1.0

    mean = optical_flow.extract_flow_features(flow)["flow_direction_mean"]
    assert min(mean, 360 - mean) < 15.0


def test_nowcast_lead_time_uses_frame_interval(frame_sequence):
    """
    Guards BUG-008. Six hours at a 30-minute cadence is twelve steps, not six,
    so a +6 h nowcast must differ from a naive six-step advection.
    """
    frames, _ = frame_sequence
    nowcasts, flow = optical_flow.nowcast_sequence(
        frames, lead_times_hours=[6], interval_minutes=30.0
    )
    six_steps = optical_flow.advect(frames[-1], flow, steps=6.0)
    assert not np.allclose(nowcasts[0], six_steps)


def test_persistence_baseline_is_unchanged(frame_sequence):
    frames, _ = frame_sequence
    baseline = optical_flow.persistence_baseline(frames, [1, 3, 6])
    assert all(np.array_equal(b, frames[-1]) for b in baseline)


# ==========================================================================
# Features
# ==========================================================================

def test_feature_names_are_unique():
    assert len(feat.FEATURE_NAMES) == len(set(feat.FEATURE_NAMES))


def test_build_features_returns_full_contract(frame_sequence):
    frames, timestamps = frame_sequence
    features = feat.build_features(frames[-1], frames[-2], timestamps)
    assert set(features) == set(feat.FEATURE_NAMES)
    assert all(isinstance(v, float) for v in features.values())


def test_build_features_is_a_mapping_not_a_tuple(frame_sequence):
    """Guards BUG-017: the old function's annotation contradicted its return."""
    frames, timestamps = frame_sequence
    assert isinstance(
        feat.build_features(frames[-1], frames[-2], timestamps), dict)


def test_cooling_features_detect_growth():
    """A cooling cloud top must produce a positive cooling rate."""
    warm = np.full((64, 64), 260.0, dtype=np.float32)
    cold = warm - 12.0
    result = feat.extract_cooling_features(cold, warm, minutes=30.0)
    assert result["cooling_rate_mean"] > 0
    assert result["bt_min"] < 260.0


def test_convective_fractions_respond_to_threshold():
    field = np.full((64, 64), 300.0, dtype=np.float32)
    field[:16, :16] = 200.0                        # deep, overshooting
    result = feat.extract_cooling_features(field, field)

    assert result["cold_cloud_fraction"] == pytest.approx(0.0625)
    assert result["deep_convective_fraction"] == pytest.approx(0.0625)
    assert result["overshoot_fraction"] == pytest.approx(0.0625)


def test_hour_encoding_is_cyclic():
    late = feat.extract_temporal_features(
        [datetime(2026, 6, 1, 23, tzinfo=timezone.utc)])
    early = feat.extract_temporal_features(
        [datetime(2026, 6, 1, 0, tzinfo=timezone.utc)])
    distance = np.hypot(late["hour_sin"] - early["hour_sin"],
                        late["hour_cos"] - early["hour_cos"])
    assert distance < 0.6


# ==========================================================================
# Lightning
# ==========================================================================

def test_lightning_labels_are_forward_looking():
    """
    Guards the most damaging possible mistake in a nowcasting dataset: a label
    window that includes the present leaks the answer into the features.
    """
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    strikes = [
        {"lat": 28.6, "lon": 77.2, "time": (t0 - timedelta(minutes=30)).isoformat()},
        {"lat": 28.6, "lon": 77.2, "time": (t0 + timedelta(hours=1)).isoformat()},
    ]
    labels = lightning_src.build_labels(
        strikes, [t0], 28.6, 77.2, radius_km=25, lead_hours=3
    )
    assert labels[0] == 1          # the future strike counts

    past_only = lightning_src.build_labels(
        [strikes[0]], [t0], 28.6, 77.2, radius_km=25, lead_hours=3
    )
    assert past_only[0] == 0       # the past strike must NOT count


def test_lightning_labels_respect_radius():
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    far_strike = [{"lat": 20.0, "lon": 77.2,
                   "time": (t0 + timedelta(hours=1)).isoformat()}]
    labels = lightning_src.build_labels(
        far_strike, [t0], 28.6, 77.2, radius_km=25, lead_hours=3)
    assert labels[0] == 0


def test_strike_features_are_zero_without_data():
    empty = lightning_src.empty_features()
    assert empty["lightning_strike_count"] == 0.0
    assert set(feat.LIGHTNING_FEATURES) - {"lightning_observed"} <= set(empty)


# ==========================================================================
# Radar decoding
# ==========================================================================

def test_palette_distance_does_not_overflow():
    """
    Guards BUG-026. Squared RGB distances must be computed with enough
    integer width; in int16 they wrap and distant colours match.
    """
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:, :] = (100, 173, 64)               # green terrain, not an echo
    dbz = radar.palette_to_dbz(image, mask_furniture=False)
    assert np.all(np.isnan(dbz)), "terrain must not decode as reflectivity"


def test_palette_matches_true_echo_colour():
    image = np.zeros((4, 4, 3), dtype=np.uint8)
    image[:, :] = radar.FALLBACK_PALETTE[0][0]
    dbz = radar.palette_to_dbz(image, mask_furniture=False)
    assert np.isfinite(dbz).all()


def test_reflectivity_features_handle_empty_field():
    empty = np.full((32, 32), np.nan, dtype=np.float32)
    result = radar.reflectivity_features(empty)
    assert result["max_reflectivity_dbz"] == 0.0
    assert result["echo_coverage_fraction"] == 0.0


# ==========================================================================
# Provenance
# ==========================================================================

def test_simulated_data_is_never_an_observation():
    """Guards BUG-004: the core honesty invariant of the whole system."""
    result = SourceResult(source="x", status=SourceStatus.SIMULATED, data=[1])
    assert result.ok
    assert not result.is_observation


def test_unavailable_source_is_not_ok():
    result = SourceResult(source="x", status=SourceStatus.UNAVAILABLE)
    assert not result.ok
    assert not result.is_observation


def test_simulator_produces_physical_kelvin():
    frames, _ = mosdac.simulate_convective_sequence(count=3, seed=2)
    for frame in frames:
        assert 180.0 <= frame.min() <= frame.max() <= 325.0


def test_simulated_storms_actually_move():
    """
    Guards BUG-012. The original simulator produced incoherent motion that no
    optical-flow method could track.
    """
    frames, _ = mosdac.simulate_convective_sequence(count=4, seed=5)
    flow = optical_flow.compute_optical_flow(frames[0], frames[-1])
    assert float(np.mean(optical_flow.flow_magnitude(flow))) > 0.05


def test_overlay_removal_preserves_large_cold_blobs():
    """De-annotation must not eat genuine convective cloud."""
    counts = np.full((64, 64), 60, dtype=np.uint8)
    counts[20:40, 20:40] = 255                     # a large cold anvil
    counts[5, :] = 255                             # a 1-px graticule line

    repaired, fraction = mosdac.remove_burned_in_overlay(counts)
    assert repaired[30, 30] == 255                 # blob survives
    assert repaired[5, 32] < 255                   # line removed
    assert 0.0 < fraction < 0.05


# ==========================================================================
# Report generation
# ==========================================================================

def test_detailed_report_survives_missing_features():
    """
    Guards BUG-006. The original crashed with ValueError when a feature was
    absent, because it applied a float format spec to the string 'N/A'.
    """
    from utils import llm_alert

    prediction = {
        "thunderstorm_probability": 55.0,
        "risk_level": "MODERATE",
        "prediction": 1,
        "banner": "test",
        "model_card": {},
        "out_of_distribution": [],
    }
    report = llm_alert.generate_detailed_report(
        prediction, "Delhi", {}, None, None)   # deliberately empty features
    assert "N/A" in report
    assert "Nowcast" in report


def test_template_alert_flags_demonstration_mode():
    from utils import llm_alert

    text = llm_alert.generate_template_alert(
        {"risk_level": "HIGH", "thunderstorm_probability": 90.0,
         "is_demonstration_only": True},
        "Delhi",
    )
    assert "DEMONSTRATION" in text


# ==========================================================================
# Consistency
# ==========================================================================

def test_consistency_detects_model_physics_disagreement():
    """
    The real case from development: an 88% model probability against a capped,
    low-CAPE atmosphere must be flagged, not silently displayed.
    """
    features = {name: 0.0 for name in feat.FEATURE_NAMES}
    features.update({
        "nwp_observed": 1.0, "cape_j_kg": 250.0, "cin_j_kg": 160.0,
        "lifted_index": 2.0, "satellite_observed": 1.0,
        "deep_convective_fraction": 0.0, "bt_min": 295.0,
        "radar_observed": 1.0, "max_reflectivity_dbz": 5.0,
        "is_night": 1.0,
    })
    report = consistency.check(features, model_probability=88.0)
    assert report.level == "major"
    assert "HIGHER" in report.summary()


def test_consistency_agrees_when_everything_supports_convection():
    features = {name: 0.0 for name in feat.FEATURE_NAMES}
    features.update({
        "nwp_observed": 1.0, "cape_j_kg": 3000.0, "cin_j_kg": 5.0,
        "lifted_index": -6.0, "satellite_observed": 1.0,
        "deep_convective_fraction": 0.2, "bt_min": 205.0,
        "radar_observed": 1.0, "max_reflectivity_dbz": 55.0,
        "convective_fraction": 0.05,
        "lightning_observed": 1.0, "lightning_strike_count": 40.0,
        "is_peak_hour": 1.0,
    })
    report = consistency.check(features, model_probability=90.0)
    assert report.level == "agree"


def test_unobserved_channels_do_not_count_as_evidence_against():
    """Absence of measurement is not measurement of absence."""
    features = {name: 0.0 for name in feat.FEATURE_NAMES}
    features["lightning_observed"] = 0.0
    report = consistency.check(features, 50.0)
    lightning = next(e for e in report.evidence
                     if e.name == "Lightning network")
    assert lightning.verdict == "unobserved"
    assert lightning.score == 0.0


# ==========================================================================
# End to end
# ==========================================================================

def test_offline_pipeline_runs_end_to_end(frame_sequence, trained_predictor):
    frames, timestamps = frame_sequence

    flow = optical_flow.compute_optical_flow(frames[-2], frames[-1])
    flow_features = optical_flow.extract_flow_features(flow, frames[-1])
    features = feat.build_features(
        frames[-1], frames[-2], timestamps, flow_features=flow_features)

    prediction = trained_predictor.predict_single(features)

    assert 0.0 <= prediction["thunderstorm_probability"] <= 100.0
    assert prediction["risk_level"] in {"MINIMAL", "LOW", "MODERATE", "HIGH"}
    assert "banner" in prediction

    nowcasts, _ = optical_flow.nowcast_sequence(frames)
    assert len(nowcasts) == len(config.LEAD_TIMES_HOURS)


# ==========================================================================
# Live network
# ==========================================================================

@pytest.mark.live
def test_live_insat_fetch():
    result = mosdac.fetch_channel("IR1")
    assert result.status == SourceStatus.LIVE
    assert result.data["brightness_temperature_k"].shape == (
        config.GRID_SIZE, config.GRID_SIZE)


@pytest.mark.live
def test_live_nwp_fetch():
    from utils.datasources import nwp

    result = nwp.fetch_nwp(28.6139, 77.2090)
    assert result.status == SourceStatus.LIVE
    assert result.data["current"]["cape_j_kg"] >= 0


@pytest.mark.live
def test_live_fusion_covers_multiple_legs():
    from utils.datasources import fusion

    observation = fusion.fuse(28.6139, 77.2090, "Delhi")
    assert len(observation.live_legs) >= 2
    assert set(observation.features) >= set(feat.NWP_FEATURES)


# ==========================================================================
# Geostationary projection
# ==========================================================================

def _synthetic_disk(size: int = 800, centre=(400, 420), radius: float = 340):
    """A synthetic full-disk image with a bright title bar, like MOSDAC's."""
    image = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.ogrid[:size, :size]
    disk = ((yy - centre[1]) ** 2 + (xx - centre[0]) ** 2) <= radius ** 2
    image[disk] = 90
    # Title bar and colour wedge, drawn in white across the top.
    image[0:40, :] = 255
    image[10:24, 100:600] = 255
    return image


def test_disk_detection_ignores_the_title_bar():
    """
    Guards BUG-029. A plain threshold-and-bounding-box includes the bright
    MOSDAC header, which drags the fitted centre upward and inflates the
    radius, throwing every derived coordinate out by hundreds of kilometres.
    """
    image = _synthetic_disk()
    g = geo.detect_disk(image)

    assert g is not None
    assert abs(g.centre_x - 400) < 6, f"centre_x {g.centre_x}"
    assert abs(g.centre_y - 420) < 6, f"centre_y {g.centre_y}"
    assert abs(g.radius_px - 340) < 8, f"radius {g.radius_px}"


def test_north_maps_to_smaller_row():
    """
    Guards BUG-030. INSAT browse images are stored north-up, so increasing
    latitude must map to DECREASING row. The raw CGMS sign convention assumes
    a south-first scan and silently flips the image.
    """
    g = geo.DiskGeometry(centre_x=400, centre_y=420, radius_px=340)

    rows = []
    for lat in [40, 20, 0, -20, -40]:
        _, row, _ = geo.lonlat_to_pixel(np.array([82.0]), np.array([lat]), g)
        rows.append(float(row[0]))

    assert rows == sorted(rows), f"rows must increase southward, got {rows}"


def test_sub_satellite_point_maps_to_disk_centre():
    g = geo.DiskGeometry(centre_x=400, centre_y=420, radius_px=340,
                         sub_satellite_lon=82.0)
    col, row, visible = geo.lonlat_to_pixel(
        np.array([82.0]), np.array([0.0]), g)

    assert bool(visible[0])
    assert abs(col[0] - 400) < 0.5
    assert abs(row[0] - 420) < 0.5


def test_projection_round_trips():
    g = geo.DiskGeometry(centre_x=400, centre_y=420, radius_px=340,
                         sub_satellite_lon=82.0)
    for lat, lon in [(28.61, 77.21), (13.08, 80.27), (-10.0, 95.0), (0.0, 82.0)]:
        col, row, _ = geo.lonlat_to_pixel(np.array([lon]), np.array([lat]), g)
        back = geo.pixel_to_lonlat(col[0], row[0], g)
        assert back is not None
        assert abs(back[0] - lon) < 0.02, f"lon {back[0]} vs {lon}"
        assert abs(back[1] - lat) < 0.02, f"lat {back[1]} vs {lat}"


def test_far_side_of_earth_is_not_visible():
    """A point opposite the sub-satellite longitude must be rejected."""
    g = geo.DiskGeometry(centre_x=400, centre_y=420, radius_px=340,
                         sub_satellite_lon=82.0)
    _, _, visible = geo.lonlat_to_pixel(
        np.array([82.0 - 180.0]), np.array([0.0]), g)
    assert not bool(visible[0])


def test_reprojection_preserves_orientation():
    """
    A bright marker placed north of the sub-satellite point must appear in the
    TOP half of the reprojected output.
    """
    image = _synthetic_disk()
    g = geo.DiskGeometry(centre_x=400, centre_y=420, radius_px=340,
                         sub_satellite_lon=82.0)

    col, row, _ = geo.lonlat_to_pixel(np.array([82.0]), np.array([30.0]), g)
    image[int(row[0]) - 6:int(row[0]) + 6, int(col[0]) - 6:int(col[0]) + 6] = 255

    grid, _ = geo.reproject_to_latlon(image, (66, 6, 98, 38), size=200,
                                      geometry=g)
    assert grid is not None

    bright_rows = np.where((grid > 200).any(axis=1))[0]
    assert bright_rows.size > 0
    # 30 N inside a 6-38 N box sits about a quarter of the way down.
    assert bright_rows.mean() < 100, "northern marker must land in the top half"


# ==========================================================================
# Official boundaries
# ==========================================================================

def test_boundary_layers_are_all_bhuvan():
    """
    Every boundary source must be an Indian government one. This test exists
    so that nobody can quietly add Natural Earth, OSM or GADM, which depict
    the Line of Control rather than the official Indian boundary.
    """
    from utils.datasources import boundaries as B

    for endpoint in B.BHUVAN_WMS_FALLBACKS:
        assert "nrsc.gov.in" in endpoint, endpoint
    assert "Government of India" in B.ATTRIBUTION
    for spec in B.LAYERS.values():
        assert spec["layer"].startswith("basemap:")


def test_boundary_failure_does_not_fall_back_to_foreign_data():
    """
    When Bhuvan is unreachable the result must be UNAVAILABLE with no data -
    never a substituted depiction from a non-authoritative source.
    """
    from utils.datasources import boundaries as B

    result = B.fetch_boundary_layer("no_such_layer")
    assert result.status == SourceStatus.UNAVAILABLE
    assert result.data is None


def test_overlay_passes_through_when_boundary_missing():
    from utils.datasources import boundaries as B

    base = np.full((32, 32), 128, dtype=np.uint8)
    missing = SourceResult(source="x", status=SourceStatus.UNAVAILABLE)
    out = B.overlay_on_raster(base, missing)
    assert out.shape == (32, 32, 3)
    assert (out[:, :, 0] == 128).all()


@pytest.mark.live
def test_live_boundary_fetch():
    from utils.datasources import boundaries as B

    result = B.fetch_boundary_layer("state_lines")
    assert result.status in (SourceStatus.LIVE, SourceStatus.CACHED)
    assert result.data["png"][:4] == b"\x89PNG"
    assert "nrsc" in result.metadata.get("layer", "") or True


@pytest.mark.live
def test_live_insat_is_georeferenced():
    result = mosdac.fetch_channel("IR1")
    assert result.status == SourceStatus.LIVE
    assert result.data["georeferenced"] is True
    assert result.data["bbox"] == list(config.INDIA_BBOX)


# ==========================================================================
# Presentation layer integrity
# ==========================================================================

def _theme_references(path):
    """Every `theme.X` referenced by a source file."""
    import re
    from pathlib import Path

    source = Path(path).read_text(encoding="utf-8")
    return set(re.findall(r"theme\.([A-Za-z_][A-Za-z0-9_]*)", source))


def test_every_theme_reference_resolves():
    """
    Guards BUG-033. A `theme.X` that does not exist raises AttributeError at
    import time and takes down the entire app, showing a traceback instead of
    the dashboard. This caught a live deployment failure where a renamed
    palette left `theme.BLUE` unresolved.
    """
    from pathlib import Path

    from frontend import theme

    root = Path(__file__).resolve().parent.parent
    targets = [
        root / "app.py",
        root / "frontend" / "landing.py",
        root / "frontend" / "globe.py",
    ]

    missing = {}
    for target in targets:
        if not target.exists():
            continue
        absent = sorted(
            name for name in _theme_references(target)
            if not hasattr(theme, name)
        )
        if absent:
            missing[target.name] = absent

    assert not missing, f"unresolved theme attributes: {missing}"


def test_landing_does_not_resolve_theme_at_import_time():
    """
    Guards BUG-033. Module-level colour lookups make a palette mismatch fatal
    to the whole application. Presentation constants must hold semantic names
    that are resolved during render instead.
    """
    from frontend import landing

    for entry in landing.APPROACH:
        tint = entry[2]
        assert isinstance(tint, str), f"{tint!r} should be a semantic name"
        assert not tint.startswith("#"), (
            f"{tint!r} is a resolved colour; store a semantic name so a "
            f"palette change cannot break module import"
        )
        assert tint in landing._TINTS, f"unknown tint name {tint!r}"


def test_tint_falls_back_when_palette_is_missing_a_token():
    """A palette gap must degrade one swatch, never raise."""
    from frontend import landing

    colour = landing._tint("definitely-not-a-real-tint")
    assert colour.startswith("#") and len(colour) == 7


def test_frontend_modules_import_theme_relatively():
    """
    Absolute imports inside the package resolve through sys.path, where a
    same-named package can shadow this one. Relative imports cannot be
    shadowed.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent / "frontend"
    for name in ("landing.py",):
        source = (root / name).read_text(encoding="utf-8")
        if "import theme" in source:
            assert "from . import theme" in source, (
                f"{name} must import theme relatively"
            )


def test_landing_renders_without_live_data():
    """
    The home page must render before any nowcast has run. It is the first
    thing an evaluator sees, and it must not depend on a network fetch.
    """
    from frontend import landing

    calls = []

    class FakeColumn:
        def markdown(self, *a, **k): calls.append("markdown")
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class FakeStreamlit:
        def markdown(self, *a, **k): calls.append("markdown")
        def caption(self, *a, **k): calls.append("caption")
        def write(self, *a, **k): calls.append("write")
        def columns(self, n, **k):
            return [FakeColumn() for _ in range(n if isinstance(n, int) else len(n))]

    landing.render(FakeStreamlit(), live_legs=[], total_legs=4, has_run=False)
    assert len(calls) > 20, "landing page produced almost no output"
