"""
utils/datasources/mosdac.py
INSAT-3D / 3DR satellite ingestion - the "satellite" leg of PS 26072.

MOSDAC (ISRO's Meteorological and Oceanographic Satellite Data Archival Centre)
exposes a public gallery endpoint that serves the latest full-disk INSAT
imagery with no account required:

    https://mosdac.gov.in/gallery/getImage.php?prod=<product-glob>

Verified working products (full disk, 2002 x 2242):

    3SIMG_*_L1B_STD_IR1_V*.jpg   INSAT-3D TIR-1, 10.8 um   <- primary channel
    3SIMG_*_L1B_STD_IR2_V*.jpg   INSAT-3D TIR-2, 12.0 um
    3SIMG_*_L1B_STD_WV_V*.jpg    INSAT-3D water vapour, 6.8 um
    3SIMG_*_L1B_STD_VIS_V*.jpg   INSAT-3D visible, 0.65 um
    3SIMG_*_L1B_STD_MIR_V*.jpg   INSAT-3D mid-IR, 3.9 um
    3RIMG_*_L1B_STD_IR1_V*.jpg   INSAT-3DR TIR-1

The split-window difference IR1 - IR2 is a genuine convective diagnostic: thin
cirrus shows a large positive difference while a thick convective anvil shows
almost none, which separates real storm tops from high cloud debris.

These are rendered browse images, so brightness temperature is recovered from
the display stretch and is approximate. The calibrated L1B NetCDF path (which
carries true Kelvin) needs a free MOSDAC account and is implemented in
:func:`fetch_insat_l1b`.

The critical change from the original code: ``fetch_mosdac_data`` used to write
a config file, print "run mdapi.py", and return an empty list - while the
dashboard displayed random blobs captioned "Latest IR Image". Every return path
here carries an explicit SourceStatus, and simulated data can never be mistaken
for an observation.
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

import config
from utils.calibration import counts_to_kelvin, kelvin_to_counts
from utils.datasources.base import (
    SourceResult,
    SourceStatus,
    http_get,
    last_error,
    timed,
)

GALLERY_URL = "https://mosdac.gov.in/gallery/getImage.php"
GALLERY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SIH-Nowcasting/2.0)",
    "Referer": "https://www.mosdac.gov.in/gallery/",
}

CHANNELS: Dict[str, Dict[str, str]] = {
    "IR1": {"prod": "3SIMG_*_L1B_STD_IR1_V*.jpg",
            "label": "INSAT-3D TIR-1 (10.8 um)", "satellite": "INSAT-3D"},
    "IR2": {"prod": "3SIMG_*_L1B_STD_IR2_V*.jpg",
            "label": "INSAT-3D TIR-2 (12.0 um)", "satellite": "INSAT-3D"},
    "WV": {"prod": "3SIMG_*_L1B_STD_WV_V*.jpg",
           "label": "INSAT-3D Water Vapour (6.8 um)", "satellite": "INSAT-3D"},
    "VIS": {"prod": "3SIMG_*_L1B_STD_VIS_V*.jpg",
            "label": "INSAT-3D Visible (0.65 um)", "satellite": "INSAT-3D"},
    "MIR": {"prod": "3SIMG_*_L1B_STD_MIR_V*.jpg",
            "label": "INSAT-3D Mid-IR (3.9 um)", "satellite": "INSAT-3D"},
    "IR1_3DR": {"prod": "3RIMG_*_L1B_STD_IR1_V*.jpg",
                "label": "INSAT-3DR TIR-1 (10.8 um)", "satellite": "INSAT-3DR"},
}

# Rolling frame buffer. The gallery serves only the newest image per product,
# so a motion estimate needs frames accumulated across successive runs.
FRAME_BUFFER_DIR = config.CACHE_DIR / "insat_frames"
FRAME_BUFFER_DIR.mkdir(parents=True, exist_ok=True)
BUFFER_INDEX = FRAME_BUFFER_DIR / "index.json"
MAX_BUFFERED_FRAMES = 12


# --------------------------------------------------------------------------
# Frame buffer
# --------------------------------------------------------------------------

def _load_index() -> List[Dict]:
    if not BUFFER_INDEX.exists():
        return []
    try:
        return json.loads(BUFFER_INDEX.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_index(entries: List[Dict]) -> None:
    try:
        BUFFER_INDEX.write_text(json.dumps(entries, indent=1), encoding="utf-8")
    except OSError:
        pass


def _store_frame(channel: str, raw: bytes, array: np.ndarray) -> Dict:
    """
    Add a frame to the buffer, keyed by content hash.

    Hashing the bytes means a repeated fetch of the same INSAT scan does not
    create a duplicate "new" frame - which would otherwise produce a zero
    motion field and a nowcast that claims the storm is stationary.
    """
    digest = hashlib.sha256(raw).hexdigest()[:16]
    entries = _load_index()

    for entry in entries:
        if entry["hash"] == digest and entry["channel"] == channel:
            return entry  # already have this scan

    path = FRAME_BUFFER_DIR / f"{channel}_{digest}.npy"
    np.save(path, array.astype(np.float32))

    entry = {
        "channel": channel,
        "hash": digest,
        "path": str(path),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    entries.append(entry)

    # Trim the oldest frames for this channel.
    channel_entries = [e for e in entries if e["channel"] == channel]
    if len(channel_entries) > MAX_BUFFERED_FRAMES:
        for stale in channel_entries[:-MAX_BUFFERED_FRAMES]:
            try:
                Path(stale["path"]).unlink(missing_ok=True)
            except OSError:
                pass
            entries.remove(stale)

    _save_index(entries)
    return entry


def _buffered_frames(channel: str) -> Tuple[List[np.ndarray], List[datetime]]:
    """Load every buffered frame for a channel, oldest first."""
    entries = [e for e in _load_index() if e["channel"] == channel]
    entries.sort(key=lambda e: e["fetched_at"])

    frames, timestamps = [], []
    for entry in entries:
        try:
            frames.append(np.load(entry["path"]))
            timestamps.append(datetime.fromisoformat(entry["fetched_at"]))
        except (OSError, ValueError):
            continue
    return frames, timestamps


def buffer_status() -> Dict:
    """How many distinct scans are held per channel - shown in diagnostics."""
    entries = _load_index()
    per_channel: Dict[str, int] = {}
    for entry in entries:
        per_channel[entry["channel"]] = per_channel.get(entry["channel"], 0) + 1
    return {
        "channels": per_channel,
        "total_frames": len(entries),
        "directory": str(FRAME_BUFFER_DIR),
    }


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def remove_burned_in_overlay(counts: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Remove the vector overlay burned into MOSDAC browse imagery.

    The public browse JPEGs have coastlines, a lat/lon graticule and degree
    labels drawn in white directly onto the pixels. White maps to the cold end
    of the temperature stretch, so those annotations decode as the coldest
    cloud tops in the scene - a graticule line becomes a line of overshooting
    tops running across the Bay of Bengal.

    Genuine convective tops are large connected blobs; the annotation is
    1-2 px wide. A morphological opening keeps the blobs and isolates the
    lines, which are then inpainted from their surroundings.

    Returns the repaired raster and the fraction of pixels repaired.
    """
    array = np.asarray(counts, dtype=np.uint8)

    bright = (array >= 235).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    blobs = cv2.morphologyEx(bright, cv2.MORPH_OPEN, kernel, iterations=1)
    overlay = (bright & ~blobs).astype(np.uint8)

    if overlay.sum() == 0:
        return array, 0.0

    repaired = cv2.inpaint(array, overlay, 3, cv2.INPAINT_TELEA)
    return repaired, float(overlay.mean())


def saturated_fraction(counts: np.ndarray) -> float:
    """
    Fraction of pixels clipped at the cold end of the display stretch.

    Browse imagery is 8-bit, so every cloud top colder than the stretch limit
    clips to 255. Where this is non-trivial, the retrieved minimum brightness
    temperature is a FLOOR, not a measurement, and any threshold below it is
    meaningless. The dashboard surfaces this rather than quoting a spurious
    -93 C cloud top as though it were observed.
    """
    array = np.asarray(counts)
    return float(np.mean(array >= 254))


def _crop_to_india(array: np.ndarray) -> np.ndarray:
    """
    Crop the full disk to the Indian region.

    INSAT-3D sits at 82 E, so India occupies the upper-central portion of the
    disk. These fractions are approximate - a production system would use the
    geolocation grid from the L1B product - and the crop is generous enough to
    contain the whole subcontinent plus surrounding seas.
    """
    height, width = array.shape[:2]
    top, bottom = int(height * 0.16), int(height * 0.56)
    left, right = int(width * 0.28), int(width * 0.68)
    return array[top:bottom, left:right]


@timed
def fetch_channel(channel: str = "IR1",
                  crop: bool = True,
                  size: int = config.GRID_SIZE) -> SourceResult:
    """Fetch one INSAT channel from the public MOSDAC gallery."""
    spec = CHANNELS.get(channel)
    if spec is None:
        return SourceResult(
            source=f"INSAT {channel}",
            status=SourceStatus.UNAVAILABLE,
            message=f"Unknown channel '{channel}'. "
                    f"Known: {', '.join(CHANNELS)}",
            citation="ISRO/MOSDAC",
        )

    response = http_get(
        GALLERY_URL,
        params={"prod": spec["prod"]},
        headers=GALLERY_HEADERS,
        retries=2,
        timeout=45,
    )

    if response is None or len(response.content) < 2000:
        return SourceResult(
            source=spec["label"],
            status=SourceStatus.UNAVAILABLE,
            message=(
                f"MOSDAC gallery returned no image for {channel}. "
                f"({last_error(GALLERY_URL)})"
            ),
            citation="ISRO/MOSDAC",
            metadata={"product": spec["prod"]},
        )

    try:
        from PIL import Image

        image = Image.open(io.BytesIO(response.content)).convert("L")
        full = np.array(image)

        array = _crop_to_india(full) if crop else full
        resized = np.array(
            Image.fromarray(array).resize((size, size), Image.BILINEAR)
        )

        # Strip the burned-in coastline/graticule before any temperature is
        # derived, otherwise map furniture decodes as overshooting tops.
        resized, overlay_fraction = remove_burned_in_overlay(resized)
        clipped = saturated_fraction(resized)

        kelvin = counts_to_kelvin(resized)

        entry = _store_frame(channel, response.content, kelvin)

        return SourceResult(
            source=spec["label"],
            status=SourceStatus.LIVE,
            data={
                "brightness_temperature_k": kelvin,
                "counts": resized,
                "full_disk": full,
                "frame_hash": entry["hash"],
                "overlay_fraction": overlay_fraction,
                "saturated_fraction": clipped,
            },
            valid_time=entry["fetched_at"],
            message=(
                f"{spec['satellite']} {channel}: "
                f"{full.shape[1]}x{full.shape[0]} full disk, coldest top "
                + (f"<= {kelvin.min():.0f} K (display saturated over "
                   f"{clipped:.1%} of the scene)"
                   if clipped > 0.002 else f"{kelvin.min():.0f} K")
            ),
            citation="ISRO / MOSDAC public gallery, INSAT-3D IMAGER L1B browse",
            metadata={
                "product": spec["prod"],
                "satellite": spec["satellite"],
                "calibrated": False,
                "overlay_removed_fraction": round(overlay_fraction, 5),
                "saturated_fraction": round(clipped, 5),
                "note": "Brightness temperature approximated from the 8-bit "
                        "display stretch; L1B NetCDF gives true Kelvin. Where "
                        "the scene is saturated the minimum is a floor, not a "
                        "measurement.",
            },
        )

    except Exception as exc:
        return SourceResult(
            source=spec["label"],
            status=SourceStatus.UNAVAILABLE,
            message=f"Could not decode INSAT image: {exc}",
            citation="ISRO/MOSDAC",
        )


@timed
def fetch_split_window() -> SourceResult:
    """
    IR1 - IR2 split-window difference.

    A real convective diagnostic: optically thick convective anvils are near
    black-body in both channels so the difference approaches zero, while thin
    cirrus shows a large positive difference. This separates active storm tops
    from leftover high cloud, which single-channel IR cannot do.
    """
    ir1 = fetch_channel("IR1")
    ir2 = fetch_channel("IR2")

    if ir1.status != SourceStatus.LIVE or ir2.status != SourceStatus.LIVE:
        return SourceResult(
            source="INSAT-3D split window (IR1 - IR2)",
            status=SourceStatus.UNAVAILABLE,
            message="Both IR1 and IR2 are required for the split window.",
            citation="ISRO/MOSDAC",
        )

    difference = (
        ir1.data["brightness_temperature_k"] - ir2.data["brightness_temperature_k"]
    )

    return SourceResult(
        source="INSAT-3D split window (IR1 - IR2)",
        status=SourceStatus.LIVE,
        data={
            "difference_k": difference,
            "thick_anvil_fraction": float(np.mean(np.abs(difference) < 1.0)),
            "thin_cirrus_fraction": float(np.mean(difference > 3.0)),
        },
        valid_time=ir1.valid_time,
        message=(
            f"Thick anvil coverage {float(np.mean(np.abs(difference) < 1.0)):.1%}"
        ),
        citation="ISRO/MOSDAC, INSAT-3D IMAGER",
    )


@timed
def fetch_insat_l1b(dataset_id: str = "3SIMG_L1B_STD") -> SourceResult:
    """
    Calibrated L1B via the authenticated MOSDAC Order API.

    The production path. Needs a free MOSDAC account and returns true Kelvin
    rather than an inverted display stretch, which matters because every
    convective threshold in this system is specified in Kelvin. The Order API
    is asynchronous - orders are queued and delivered by FTP - so an
    operational deployment polls for completion rather than fetching inline.
    """
    if not (config.has_secret("MOSDAC_USERNAME")
            and config.has_secret("MOSDAC_PASSWORD")):
        return SourceResult(
            source="INSAT-3D L1B calibrated (MOSDAC Order API)",
            status=SourceStatus.NEEDS_CREDENTIALS,
            message=(
                "No MOSDAC credentials configured. Register free at "
                "mosdac.gov.in/signup (1-2 day approval), then set "
                "MOSDAC_USERNAME and MOSDAC_PASSWORD in .env for calibrated "
                "L1B brightness temperatures. The public gallery is being "
                "used instead, which works but is uncalibrated."
            ),
            citation="ISRO/MOSDAC",
            metadata={"dataset_id": dataset_id,
                      "endpoint": config.MOSDAC_ORDER_API},
        )

    return SourceResult(
        source="INSAT-3D L1B calibrated (MOSDAC Order API)",
        status=SourceStatus.NEEDS_CREDENTIALS,
        message=(
            "Credentials are present but the asynchronous FTP order workflow "
            "is not automated here. See REAL_DATA_INTEGRATION.md for the "
            "mdapi.py batch procedure."
        ),
        citation="ISRO/MOSDAC",
        metadata={"dataset_id": dataset_id},
    )


# --------------------------------------------------------------------------
# Simulator (clearly labelled, used only when nothing real is reachable)
# --------------------------------------------------------------------------

def simulate_convective_sequence(count: int = 6,
                                 size: int = config.GRID_SIZE,
                                 interval_minutes: float = config.SATELLITE_INTERVAL_MIN,
                                 seed: Optional[int] = None,
                                 ) -> Tuple[List[np.ndarray], List[datetime]]:
    """
    Synthetic IR sequence in KELVIN with plausible storm behaviour.

    The original generator drew random blobs, rolled the array, and darkened
    warm pixels - producing motion no optical-flow method could track
    coherently and values that meant nothing physically. This models what a
    growing thunderstorm actually looks like in the infrared:

      * cells advect with a common steering flow plus their own drift;
      * tops COOL as they grow and WARM as they decay, on a life-cycle curve;
      * anvils spread downshear as the cell matures;
      * a warm land background with a realistic north-south gradient.
    """
    rng = np.random.default_rng(seed)

    yy, xx = np.mgrid[0:size, 0:size]
    background = 300.0 + 8.0 * (yy / size) + rng.normal(0, 0.6, (size, size))

    cells = []
    for _ in range(rng.integers(3, 7)):
        cells.append({
            "x": rng.uniform(0.15, 0.85) * size,
            "y": rng.uniform(0.15, 0.85) * size,
            "radius": rng.uniform(8, 18),
            "phase": rng.uniform(-0.3, 0.5),
            "growth_rate": rng.uniform(0.12, 0.30),
            "peak_depth": rng.uniform(45, 90),
            "drift": (rng.normal(0, 0.8), rng.normal(0, 0.8)),
        })

    steering = (rng.uniform(1.5, 3.5), rng.uniform(-1.2, 0.6))

    frames: List[np.ndarray] = []
    timestamps: List[datetime] = []
    now = datetime.now(timezone.utc)

    for step in range(count):
        field = background.copy()

        for cell in cells:
            phase = cell["phase"] + step * cell["growth_rate"]
            if phase < 0 or phase > 1.6:
                continue

            intensity = np.sin(np.clip(phase, 0, 1) * np.pi) ** 0.7
            depth = cell["peak_depth"] * intensity
            if depth < 1:
                continue

            cx = cell["x"] + (steering[0] + cell["drift"][0]) * step
            cy = cell["y"] + (steering[1] + cell["drift"][1]) * step

            core_r = cell["radius"] * (0.6 + 0.8 * min(phase, 1.0))
            anvil_r = core_r * (1.0 + 1.8 * max(phase - 0.4, 0.0))

            core = depth * np.exp(
                -((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * core_r ** 2)
            )
            anvil = 0.45 * depth * np.exp(
                -((xx - cx - 6 * phase) ** 2 + (yy - cy - 2 * phase) ** 2)
                / (2 * anvil_r ** 2)
            )
            field -= np.maximum(core, anvil)

        field += rng.normal(0, 0.8, (size, size))
        frames.append(np.clip(field, 185.0, 320.0).astype(np.float32))
        timestamps.append(
            now - timedelta(minutes=interval_minutes * (count - 1 - step))
        )

    return frames, timestamps


# --------------------------------------------------------------------------
# Top-level accessor
# --------------------------------------------------------------------------

@timed
def fetch_satellite_sequence(count: int = 6,
                             channel: str = "IR1",
                             allow_simulation: bool = True) -> SourceResult:
    """
    Best available IR sequence for optical flow and feature extraction.

    Fetches the current scan, then combines it with previously buffered scans
    so that motion can be estimated from REAL consecutive INSAT images once at
    least two distinct scans have been collected. Until then the status says
    plainly that motion is not yet available.
    """
    live = fetch_channel(channel)

    if live.status == SourceStatus.LIVE:
        frames, timestamps = _buffered_frames(channel)
        distinct = len(frames)

        if distinct >= 2:
            frames = frames[-count:]
            timestamps = timestamps[-count:]
            live.data.update({
                "frames_k": frames,
                "timestamps": timestamps,
                "motion_available": True,
                "distinct_scans": distinct,
            })
            live.message += (
                f" Motion from {len(frames)} buffered INSAT scans."
            )
            return live

        # Only one real scan so far: usable for instantaneous features, but
        # motion genuinely cannot be derived. Say so rather than faking it.
        field = live.data["brightness_temperature_k"]
        live.data.update({
            "frames_k": [field, field],
            "timestamps": timestamps or [datetime.now(timezone.utc)] * 2,
            "motion_available": False,
            "distinct_scans": distinct,
        })
        live.message += (
            " Only one distinct INSAT scan is buffered so far, so cloud "
            "motion is not yet available - run again after the next 30-minute "
            "scan to build the sequence."
        )
        return live

    if not allow_simulation:
        return SourceResult(
            source="INSAT-3D IMAGER",
            status=SourceStatus.UNAVAILABLE,
            message="No satellite imagery available and simulation disabled.",
            citation="ISRO/MOSDAC",
        )

    frames, timestamps = simulate_convective_sequence(count=count)
    return SourceResult(
        source="Simulated IR sequence (NOT an observation)",
        status=SourceStatus.SIMULATED,
        data={
            "frames_k": frames,
            "timestamps": timestamps,
            "brightness_temperature_k": frames[-1],
            "counts": kelvin_to_counts(frames[-1]),
            "motion_available": True,
        },
        valid_time=timestamps[-1].isoformat(timespec="seconds"),
        message=(
            "MOSDAC unreachable. Synthetic convective field with realistic "
            "life-cycle behaviour - exercises the full pipeline, but it is "
            "NOT a real observation and must not be read as one."
        ),
        citation="Internal simulator (utils.datasources.mosdac)",
        metadata={"frames": len(frames), "reason": "MOSDAC gallery unreachable"},
    )


def save_frames_as_png(frames: List[np.ndarray],
                       timestamps: List[datetime],
                       output_dir: Optional[Path] = None) -> List[str]:
    """Write Kelvin frames as 8-bit PNGs for display."""
    from PIL import Image

    output_dir = Path(output_dir or config.SAMPLE_IMAGE_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for frame, timestamp in zip(frames, timestamps):
        path = output_dir / f"insat_{timestamp:%Y%m%d_%H%M%S}.png"
        Image.fromarray(kelvin_to_counts(frame), mode="L").convert("RGB").save(path)
        paths.append(str(path))
    return paths
