"""
utils/optical_flow.py
Cloud motion estimation using optical flow.
Implements Farneback dense optical flow (no training needed, runs on CPU in seconds).
"""

import cv2
import numpy as np
from typing import Tuple, List
import os


def compute_optical_flow(prev_img: np.ndarray, next_img: np.ndarray) -> np.ndarray:
    """
    Compute dense optical flow between two satellite images using Farneback method.
    
    This estimates cloud motion vectors - where clouds are moving.
    No training needed, pure mathematical computation.
    
    Args:
        prev_img: Previous satellite image (grayscale or BGR)
        next_img: Next satellite image (grayscale or BGR)
    
    Returns:
        flow: 2D array of flow vectors (H, W, 2) where flow[...,0] = x, flow[...,1] = y
    """
    # Convert to grayscale if needed
    if len(prev_img.shape) == 3:
        prev_gray = cv2.cvtColor(prev_img, cv2.COLOR_BGR2GRAY)
        next_gray = cv2.cvtColor(next_img, cv2.COLOR_BGR2GRAY)
    else:
        prev_gray = prev_img
        next_gray = next_img
    
    # Compute Farneback dense optical flow
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, next_gray, None,
        pyr_scale=0.5,     # pyramid scale factor
        levels=3,           # number of pyramid levels
        winsize=15,         # averaging window size
        iterations=3,       # iterations at each pyramid level
        poly_n=5,           # polynomial expansion neighborhood size
        poly_sigma=1.2,     # Gaussian standard deviation for polynomial expansion
        flags=0
    )
    
    return flow


def advect_image(img: np.ndarray, flow: np.ndarray, lead_time_steps: int = 1) -> np.ndarray:
    """
    Advect (move) an image along flow vectors to predict future position.
    This is the "Lagrangian persistence" nowcasting method.
    
    Args:
        img: Input image (grayscale)
        flow: Optical flow field
        lead_time_steps: Number of time steps to advect forward
    
    Returns:
        Advected image
    """
    h, w = img.shape[:2]
    
    # Create coordinate grid
    flow_map_x = np.arange(w, dtype=np.float32)
    flow_map_y = np.arange(h, dtype=np.float32)
    flow_map_x, flow_map_y = np.meshgrid(flow_map_x, flow_map_y)
    
    # Add flow to coordinates (scale by lead time)
    flow_map_x = (flow_map_x + flow[..., 0] * lead_time_steps).astype(np.float32)
    flow_map_y = (flow_map_y + flow[..., 1] * lead_time_steps).astype(np.float32)
    
    # Remap image using new coordinates
    advected = cv2.remap(
        img.astype(np.float32),
        flow_map_x,
        flow_map_y,
        cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT
    )
    
    return advected


def compute_flow_magnitude(flow: np.ndarray) -> np.ndarray:
    """Compute magnitude of flow vectors."""
    return np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)


def compute_flow_direction(flow: np.ndarray) -> np.ndarray:
    """Compute direction of flow vectors in degrees."""
    return np.degrees(np.arctan2(flow[..., 1], flow[..., 0]))


def extract_flow_features(flow: np.ndarray, img: np.ndarray) -> dict:
    """
    Extract statistical features from optical flow for ML model.
    
    Returns:
        Dictionary of flow features
    """
    magnitude = compute_flow_magnitude(flow)
    direction = compute_flow_direction(flow)
    
    # Convergence (negative divergence = convergence = rising air = storms)
    # Approximate divergence using finite differences
    dflow_dx = cv2.Sobel(flow[..., 0], cv2.CV_64F, 1, 0, ksize=3)
    dflow_dy = cv2.Sobel(flow[..., 1], cv2.CV_64F, 0, 1, ksize=3)
    divergence = dflow_dx + dflow_dy
    convergence = -divergence
    
    # Features
    features = {
        "flow_magnitude_mean": float(np.mean(magnitude)),
        "flow_magnitude_std": float(np.std(magnitude)),
        "flow_magnitude_max": float(np.max(magnitude)),
        "flow_direction_mean": float(np.mean(direction)),
        "flow_direction_std": float(np.std(direction)),
        "convergence_mean": float(np.mean(convergence)),
        "convergence_max": float(np.max(convergence)),
        "convergence_min": float(np.min(convergence)),
        "convergence_std": float(np.std(convergence)),
    }
    
    return features


def visualize_flow(flow: np.ndarray, img: np.ndarray = None, 
                   step: int = 16, color: tuple = (0, 255, 0)) -> np.ndarray:
    """
    Create optical flow visualization (arrows on image).
    
    Args:
        flow: Optical flow field
        img: Background image (optional)
        step: Sampling step for arrows
        color: Arrow color (BGR)
    
    Returns:
        Visualization image
    """
    if img is None:
        h, w = flow.shape[:2]
        vis = np.zeros((h, w, 3), dtype=np.uint8)
    else:
        vis = img.copy() if len(img.shape) == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    h, w = flow.shape[:2]
    y, x = np.mgrid[step/2:h:step, step/2:w:step].reshape(2, -1).astype(int)
    fx, fy = flow[y, x].T
    
    lines = np.vstack([x, y, x+fx, y+fy]).T.reshape(-1, 2, 2)
    lines = np.int32(lines + 0.5)
    
    for (x1, y1), (x2, y2) in lines:
        cv2.arrowedLine(vis, (x1, y1), (x2, y2), color, 1, tipLength=0.3)
    
    return vis


def create_nowcast_sequence(images: List[np.ndarray], lead_times: List[int] = None) -> List[np.ndarray]:
    """
    Create a sequence of nowcast images for multiple lead times.
    
    Args:
        images: List of satellite images (chronological order)
        lead_times: List of lead time steps to predict
    
    Returns:
        List of nowcast images
    """
    if lead_times is None:
        lead_times = [1, 2, 3, 4, 5, 6]  # 6 hours ahead (assuming 1hr steps)
    
    # Compute flow from last two images
    flow = compute_optical_flow(images[-2], images[-1])
    
    nowcasts = []
    for lt in lead_times:
        nowcast = advect_image(images[-1], flow, lead_time_steps=lt)
        nowcasts.append(nowcast)
    
    return nowcasts


if __name__ == "__main__":
    # Test with sample images
    from satellite import generate_sample_satellite_images
    
    image_paths, timestamps = generate_sample_satellite_images(count=6)
    
    # Load images
    images = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in image_paths]
    
    # Compute optical flow
    flow = compute_optical_flow(images[-2], images[-1])
    
    # Extract features
    features = extract_flow_features(flow, images[-1])
    
    print("✅ Optical flow computed")
    print(f"   Flow shape: {flow.shape}")
    print(f"   Features: {features}")
    
    # Create nowcasts
    nowcasts = create_nowcast_sequence(images, lead_times=[1, 3, 6])
    print(f"   Generated {len(nowcasts)} nowcast frames")
