#!/usr/bin/env python3
"""
Visualize SparseDriveV2 / NAVSIM data and model predictions.

Workflow (aligned with plaza/SparseDrive/tools/visualization/visualize.py):
  1. Load scenes via SceneLoader
  2. Optionally run SparseDrive agent or load precomputed trajectories
  3. Render composite frames (cameras | BEV pred | BEV GT)
  4. Export MP4 under --out-dir

Examples:
  # GT + sensors only (navmini)
  python tools/visualization/visualize.py --split mini --max-scenes 5

  # With trained checkpoint
  python tools/visualization/visualize.py --split mini --max-scenes 3 \\
      --checkpoint exp/.../periodic_pdm_ckpts/ep0010.ckpt

  # From evaluation predictions pickle (token -> Trajectory)
  python tools/visualization/visualize.py --split mini \\
      --predictions-pkl work_dirs/predictions.pkl
"""

from __future__ import annotations

import argparse
import logging
import os
import pickle
import sys
from pathlib import Path
from typing import Dict, List, Optional

from hydra.utils import instantiate
from omegaconf import OmegaConf
from tqdm import tqdm

import cv2
import torch

# Repo root on PYTHONPATH (see scripts/visualize.sh)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from navsim.agents.abstract_agent import AbstractAgent
from navsim.common.dataclasses import Scene, SceneFilter, SensorConfig, Trajectory
from navsim.common.dataloader import SceneLoader
from navsim.visualization.config import BEV_PLOT_CONFIG

from tools.visualization.renderer import (
    add_frame_label,
    compute_agent_trajectory,
    frame_indices_for_scene,
    render_combined_frame,
)
from tools.visualization.video import combine_dir_to_video

logger = logging.getLogger(__name__)

_CONFIG_ROOT = _REPO_ROOT / "navsim/planning/script/config"
_AGENT_CONFIG = _CONFIG_ROOT / "common/agent/sparsedrive_agent.yaml"
_SCENE_FILTER_DIR = _CONFIG_ROOT / "common/train_test_split/scene_filter"


def _load_scene_filter(split_name: str, max_scenes: Optional[int], tokens: Optional[List[str]]) -> SceneFilter:
    filter_path = _SCENE_FILTER_DIR / f"{split_name}.yaml"
    if not filter_path.is_file():
        raise FileNotFoundError(
            f"Scene filter not found: {filter_path}. "
            f"Available: {[p.stem for p in _SCENE_FILTER_DIR.glob('*.yaml')]}"
        )
    cfg = OmegaConf.load(filter_path)
    scene_filter: SceneFilter = instantiate(cfg)
    if max_scenes is not None:
        scene_filter.max_scenes = max_scenes
    if tokens:
        scene_filter.tokens = tokens
    return scene_filter


def _build_scene_loader(split: str, scene_filter: SceneFilter) -> SceneLoader:
    data_root = Path(os.environ.get("OPENSCENE_DATA_ROOT", ""))
    if not data_root.is_dir():
        raise EnvironmentError(
            "OPENSCENE_DATA_ROOT is not set or invalid. "
            "Source set_env_val.sh or scripts/mini/env.sh before running."
        )
    log_path = data_root / "navsim_logs" / split
    sensor_path = data_root / "sensor_blobs" / split
    if not log_path.is_dir():
        raise FileNotFoundError(f"Missing navsim logs: {log_path}")
    if not sensor_path.is_dir():
        raise FileNotFoundError(f"Missing sensor blobs: {sensor_path}")

    return SceneLoader(
        data_path=log_path,
        original_sensor_path=sensor_path,
        scene_filter=scene_filter,
        sensor_config=SensorConfig.build_all_sensors(),
    )


def _load_agent(checkpoint: str, dataset_version: str) -> AbstractAgent:
    if not _AGENT_CONFIG.is_file():
        raise FileNotFoundError(f"Agent config missing: {_AGENT_CONFIG}")
    agent_cfg = OmegaConf.load(_AGENT_CONFIG)
    agent_cfg.checkpoint_path = checkpoint
    OmegaConf.update(agent_cfg, "config.dataset_version", dataset_version)
    agent: AbstractAgent = instantiate(agent_cfg)
    agent.initialize()
    if torch.cuda.is_available():
        agent = agent.cuda()
    agent.eval()
    return agent


def _load_predictions_pkl(path: Path) -> Dict[str, Trajectory]:
    with open(path, "rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict token->Trajectory in {path}")
    return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visualize SparseDriveV2 scenes and model outputs")
    parser.add_argument(
        "--split",
        default="mini",
        help="OpenScene split folder name (mini, trainval, test, ...)",
    )
    parser.add_argument(
        "--scene-filter",
        default="navmini",
        help="YAML name under config/.../scene_filter/ (without .yaml)",
    )
    parser.add_argument("--token", action="append", default=None, help="Scene token(s) to visualize")
    parser.add_argument("--max-scenes", type=int, default=None, help="Cap number of scenes")
    parser.add_argument("--start", type=int, default=0, help="Start index in token list")
    parser.add_argument("--end", type=int, default=None, help="End index (exclusive) in token list")
    parser.add_argument("--interval", type=int, default=1, help="Stride when iterating scenes")
    parser.add_argument(
        "--frame-mode",
        choices=("current", "history", "all"),
        default="current",
        help="current: last history frame; history: all history; all: full clip",
    )
    parser.add_argument(
        "--checkpoint",
        default=None,
        help="SparseDrive Lightning checkpoint for on-the-fly inference",
    )
    parser.add_argument(
        "--predictions-pkl",
        default=None,
        help="Pickle dict {token: Trajectory} from evaluation predict step",
    )
    parser.add_argument(
        "--dataset-version",
        default="v1",
        choices=("v1", "v2"),
        help="SparseDriveConfig dataset_version when using --checkpoint",
    )
    parser.add_argument("--draw-pred", action="store_true", default=True, help="Draw prediction BEV panel")
    parser.add_argument("--no-draw-pred", action="store_false", dest="draw_pred")
    parser.add_argument(
        "--bev-layers",
        nargs="+",
        default=["map", "annotations"],
        help="BEV layers: map, annotations, lidar",
    )
    parser.add_argument("--out-dir", default="vis", help="Output directory for frames and video")
    parser.add_argument("--fps", type=int, default=12, help="Output video FPS")
    parser.add_argument("--downsample", type=int, default=4, help="Spatial downsample for video")
    parser.add_argument("--no-video", action="store_true", help="Only save JPG frames, skip MP4")
    parser.add_argument(
        "--gif",
        action="store_true",
        help="Also write animated GIF (slower, larger files)",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()

    if not os.environ.get("NUPLAN_MAPS_ROOT"):
        logger.warning("NUPLAN_MAPS_ROOT is unset; map layers may fail.")

    BEV_PLOT_CONFIG["layers"] = list(args.bev_layers)

    scene_filter = _load_scene_filter(args.scene_filter, args.max_scenes, args.token)
    scene_loader = _build_scene_loader(args.split, scene_filter)
    tokens = scene_loader.tokens
    logger.info("Loaded %d scenes (split=%s, filter=%s)", len(tokens), args.split, args.scene_filter)

    end = args.end if args.end is not None else len(tokens)
    token_slice = tokens[args.start : end : args.interval]

    agent: Optional[AbstractAgent] = None
    if args.checkpoint:
        logger.info("Loading agent from %s", args.checkpoint)
        agent = _load_agent(args.checkpoint, args.dataset_version)

    predictions: Dict[str, Trajectory] = {}
    if args.predictions_pkl:
        predictions = _load_predictions_pkl(Path(args.predictions_pkl))
        logger.info("Loaded %d trajectories from %s", len(predictions), args.predictions_pkl)

    out_dir = Path(args.out_dir)
    combine_dir = out_dir / "combine"
    combine_dir.mkdir(parents=True, exist_ok=True)

    frame_counter = 0
    for token in tqdm(token_slice, desc="Scenes"):
        scene: Scene = scene_loader.get_scene_from_token(token)
        human_traj = scene.get_future_trajectory()

        agent_traj: Optional[Trajectory] = None
        if token in predictions:
            agent_traj = predictions[token]
        elif agent is not None:
            agent_traj = compute_agent_trajectory(agent, scene)

        indices = frame_indices_for_scene(scene, args.frame_mode)
        for frame_idx in indices:
            # Agent trajectory is defined at the planning frame (last history step)
            use_agent = agent_traj if frame_idx == scene.scene_metadata.num_history_frames - 1 else None
            image = render_combined_frame(
                scene,
                frame_idx,
                human_trajectory=human_traj,
                agent_trajectory=use_agent,
                draw_pred=args.draw_pred,
            )
            label = f"{token[:12]} f{frame_idx}"
            image = add_frame_label(image, label)
            save_path = combine_dir / f"{frame_counter:05d}.jpg"
            cv2.imwrite(str(save_path), image)
            frame_counter += 1

    if frame_counter == 0:
        logger.error("No frames rendered; check paths, tokens, and data split.")
        sys.exit(1)

    logger.info("Saved %d frames to %s", frame_counter, combine_dir)

    if not args.no_video:
        video_path = combine_dir_to_video(
            combine_dir,
            out_dir / "video.mp4",
            fps=args.fps,
            downsample=args.downsample,
        )
        logger.info("Wrote video: %s", video_path)

    if args.gif:
        from navsim.visualization.plots import frame_plot_to_gif, plot_cameras_frame_with_annotations

        gif_path = out_dir / "preview.gif"
        scene = scene_loader.get_scene_from_token(token_slice[0])
        indices = frame_indices_for_scene(scene, args.frame_mode)
        frame_plot_to_gif(
            str(gif_path),
            plot_cameras_frame_with_annotations,
            scene,
            indices,
            duration=int(1000 / max(args.fps, 1)),
        )
        logger.info("Wrote GIF preview: %s", gif_path)


if __name__ == "__main__":
    main()
