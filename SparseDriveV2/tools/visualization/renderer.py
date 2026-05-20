"""Render NAVSIM / SparseDriveV2 scenes to composite images."""

from __future__ import annotations

import io
from pathlib import Path
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import matplotlib.pyplot as plt
import numpy as np
import torch

from navsim.agents.abstract_agent import AbstractAgent
from navsim.common.dataclasses import Scene, Trajectory
from navsim.planning.training.dataset import load_feature_target_from_pickle

logger = logging.getLogger(__name__)
from navsim.visualization.bev import (
    add_annotations_to_bev_ax,
    add_configured_bev_on_ax,
    add_trajectory_to_bev_ax,
)
from navsim.visualization.camera import add_annotations_to_camera_ax
from navsim.visualization.config import BEV_PLOT_CONFIG, CAMERAS_PLOT_CONFIG, TRAJECTORY_CONFIG
from navsim.visualization.plots import configure_all_ax, configure_ax, configure_bev_ax


def _fig_to_bgr(fig: plt.Figure) -> np.ndarray:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0)
    buf.seek(0)
    data = np.frombuffer(buf.getvalue(), dtype=np.uint8)
    buf.close()
    plt.close(fig)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError("Failed to decode matplotlib figure to image.")
    return image


def _resize_to_height(image: np.ndarray, target_height: int) -> np.ndarray:
    height, width = image.shape[:2]
    if height == target_height:
        return image
    scale = target_height / height
    new_width = max(1, int(width * scale))
    return cv2.resize(image, (new_width, target_height), interpolation=cv2.INTER_AREA)


def plot_cameras_with_annotations(scene: Scene, frame_idx: int) -> np.ndarray:
    """8 cameras + center BEV in 3x3 grid, return BGR image."""
    frame = scene.frames[frame_idx]
    fig, ax = plt.subplots(3, 3, figsize=CAMERAS_PLOT_CONFIG["figure_size"])

    add_annotations_to_camera_ax(ax[0, 0], frame.cameras.cam_l0, frame.annotations)
    add_annotations_to_camera_ax(ax[0, 1], frame.cameras.cam_f0, frame.annotations)
    add_annotations_to_camera_ax(ax[0, 2], frame.cameras.cam_r0, frame.annotations)
    add_annotations_to_camera_ax(ax[1, 0], frame.cameras.cam_l1, frame.annotations)
    add_configured_bev_on_ax(ax[1, 1], scene.map_api, frame)
    add_annotations_to_camera_ax(ax[1, 2], frame.cameras.cam_r1, frame.annotations)
    add_annotations_to_camera_ax(ax[2, 0], frame.cameras.cam_l2, frame.annotations)
    add_annotations_to_camera_ax(ax[2, 1], frame.cameras.cam_b0, frame.annotations)
    add_annotations_to_camera_ax(ax[2, 2], frame.cameras.cam_r2, frame.annotations)

    configure_all_ax(ax)
    configure_bev_ax(ax[1, 1])
    fig.tight_layout()
    fig.subplots_adjust(wspace=0.01, hspace=0.01, left=0.01, right=0.99, top=0.99, bottom=0.01)
    return _fig_to_bgr(fig)


def plot_bev_gt(scene: Scene, frame_idx: int, human_trajectory: Optional[Trajectory] = None) -> np.ndarray:
    """BEV with map, annotations, and optional human (GT) future trajectory."""
    frame = scene.frames[frame_idx]
    fig, ax = plt.subplots(1, 1, figsize=BEV_PLOT_CONFIG["figure_size"])
    add_configured_bev_on_ax(ax, scene.map_api, frame)
    if human_trajectory is not None:
        add_trajectory_to_bev_ax(ax, human_trajectory, TRAJECTORY_CONFIG["human"])
    configure_bev_ax(ax)
    configure_ax(ax)
    return _fig_to_bgr(fig)


def plot_bev_pred(
    scene: Scene,
    frame_idx: int,
    human_trajectory: Optional[Trajectory] = None,
    agent_trajectory: Optional[Trajectory] = None,
) -> np.ndarray:
    """BEV with map, annotations, human GT and model prediction trajectories."""
    frame = scene.frames[frame_idx]
    fig, ax = plt.subplots(1, 1, figsize=BEV_PLOT_CONFIG["figure_size"])
    add_configured_bev_on_ax(ax, scene.map_api, frame)
    add_annotations_to_bev_ax(ax, frame.annotations)
    if human_trajectory is not None:
        add_trajectory_to_bev_ax(ax, human_trajectory, TRAJECTORY_CONFIG["human"])
    if agent_trajectory is not None:
        add_trajectory_to_bev_ax(ax, agent_trajectory, TRAJECTORY_CONFIG["agent"])
    configure_bev_ax(ax)
    configure_ax(ax)
    return _fig_to_bgr(fig)


def render_combined_frame(
    scene: Scene,
    frame_idx: int,
    human_trajectory: Optional[Trajectory] = None,
    agent_trajectory: Optional[Trajectory] = None,
    draw_pred: bool = True,
) -> np.ndarray:
    """
  SparseDrive-style layout: [cameras | BEV pred (+GT/agent) | BEV GT].
    """
    cam_bgr = plot_cameras_with_annotations(scene, frame_idx)
    human_traj = human_trajectory if human_trajectory is not None else scene.get_future_trajectory()
    bev_gt_bgr = plot_bev_gt(scene, frame_idx, human_trajectory=human_traj)

    if draw_pred and agent_trajectory is not None:
        bev_pred_bgr = plot_bev_pred(
            scene,
            frame_idx,
            human_trajectory=human_traj,
            agent_trajectory=agent_trajectory,
        )
    else:
        bev_pred_bgr = plot_bev_pred(scene, frame_idx, human_trajectory=human_traj, agent_trajectory=None)

    target_h = cam_bgr.shape[0]
    bev_pred_bgr = _resize_to_height(bev_pred_bgr, target_h)
    bev_gt_bgr = _resize_to_height(bev_gt_bgr, target_h)
    return cv2.hconcat([cam_bgr, bev_pred_bgr, bev_gt_bgr])


def frame_indices_for_scene(scene: Scene, frame_mode: str) -> List[int]:
    """Resolve which frame indices to render for a scene."""
    n_hist = scene.scene_metadata.num_history_frames
    n_total = len(scene.frames)
    if frame_mode == "current":
        return [n_hist - 1]
    if frame_mode == "history":
        return list(range(n_hist))
    if frame_mode == "all":
        return list(range(n_total))
    raise ValueError(f"Unknown frame_mode={frame_mode!r}, use current|history|all")


def _batch_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Add batch dimension for single-scene inference (matches eval DataLoader)."""
    batched: Dict[str, Any] = {}
    for key, value in features.items():
        if key == "camera_feature" and isinstance(value, dict):
            cam_batched: Dict[str, Any] = {}
            for cam_key, cam_val in value.items():
                if isinstance(cam_val, torch.Tensor):
                    cam_batched[cam_key] = cam_val.unsqueeze(0)
                elif isinstance(cam_val, np.ndarray):
                    cam_batched[cam_key] = np.expand_dims(cam_val, axis=0)
                else:
                    cam_batched[cam_key] = cam_val
            batched[key] = cam_batched
        elif isinstance(value, torch.Tensor):
            batched[key] = value.unsqueeze(0)
        else:
            batched[key] = value
    return batched


def _features_to_device(features: Dict[str, Any], device: torch.device) -> Dict[str, Any]:
    """Move tensors to device; keep image_wh as float tensor (not numpy on CPU)."""
    out: Dict[str, Any] = {}
    for key, value in features.items():
        if key == "camera_feature" and isinstance(value, dict):
            cam_out: Dict[str, Any] = {}
            for cam_key, cam_val in value.items():
                if cam_key == "image_wh":
                    if isinstance(cam_val, np.ndarray):
                        cam_out[cam_key] = torch.tensor(cam_val, dtype=torch.float32, device=device)
                    else:
                        cam_out[cam_key] = cam_val.to(device=device, dtype=torch.float32)
                elif isinstance(cam_val, torch.Tensor):
                    cam_out[cam_key] = cam_val.to(device)
                else:
                    cam_out[cam_key] = cam_val
            out[key] = cam_out
        elif isinstance(value, torch.Tensor):
            out[key] = value.to(device)
        else:
            out[key] = value
    return out


def compute_agent_trajectory(
    agent: AbstractAgent,
    scene: Scene,
    cache_path: Optional[Path] = None,
) -> Trajectory:
    """
    Run SparseDrive inference (same path as eval: cache + feature pipeline + forward).
    """
    token = scene.scene_metadata.initial_token
    log_name = scene.scene_metadata.log_name
    builders = agent.get_feature_builders()
    if not builders:
        raise RuntimeError("Agent has no feature builders; cannot run inference.")
    builder = builders[0]

    features: Optional[Dict[str, Any]] = None
    if cache_path is not None:
        feature_file = cache_path / log_name / token / f"{builder.get_unique_name()}.gz"
        if feature_file.is_file():
            features = load_feature_target_from_pickle(feature_file)
        else:
            logger.warning("Feature cache miss: %s", feature_file)

    if features is None:
        features = builder.compute_features(scene.get_agent_input())

    if hasattr(builder, "pipeline"):
        features, _, _ = builder.pipeline(features, {}, token, test_mode=True)

    features = _batch_features(features)
    device = next(agent.parameters()).device
    features = _features_to_device(features, device)

    agent.eval()
    with torch.no_grad():
        predictions, _ = agent.forward(features, None)
        poses = predictions["trajectory"].squeeze(0).detach().cpu().numpy()

    return Trajectory(poses, agent._trajectory_sampling)


def add_frame_label(image: np.ndarray, text: str) -> np.ndarray:
    """Overlay token / frame label on the composite image."""
    out = image.copy()
    cv2.putText(
        out,
        text,
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        out,
        text,
        (30, 60),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    return out
