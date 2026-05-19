"""Export rendered frames to MP4 (mirrors SparseDrive tools/visualization/visualize.py)."""

from __future__ import annotations

import glob
from pathlib import Path
from typing import Iterable, List, Optional, Union

import cv2
from tqdm import tqdm


def images_to_video(
    image_paths: Iterable[Union[str, Path]],
    output_path: Union[str, Path],
    fps: int = 12,
    downsample: int = 1,
) -> Path:
    """
    Stitch sorted images into an MP4 file.
    :param image_paths: ordered list of image paths
    :param output_path: destination .mp4 path
    :param fps: playback frames per second
    :param downsample: spatial downscale factor (1 = no resize)
    :return: output path
    """
    paths: List[Path] = [Path(p) for p in image_paths]
    if not paths:
        raise ValueError("No images provided for video export.")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    writer: Optional[cv2.VideoWriter] = None
    size = None

    for img_path in tqdm(paths, desc="Writing video"):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        if downsample > 1:
            height, width = img.shape[:2]
            img = cv2.resize(
                img,
                (width // downsample, height // downsample),
                interpolation=cv2.INTER_AREA,
            )
        if size is None:
            height, width = img.shape[:2]
            size = (width, height)
            writer = cv2.VideoWriter(
                str(output_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                fps,
                size,
            )
        if writer is None:
            continue
        if (img.shape[1], img.shape[0]) != size:
            img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
        writer.write(img)

    if writer is not None:
        writer.release()
    return output_path


def combine_dir_to_video(
    frames_dir: Union[str, Path],
    output_path: Union[str, Path],
    pattern: str = "*.jpg",
    fps: int = 12,
    downsample: int = 4,
) -> Path:
    """Glob a directory of frames and export video (SparseDrive-style helper)."""
    frames_dir = Path(frames_dir)
    image_paths = sorted(glob.glob(str(frames_dir / pattern)))
    return images_to_video(image_paths, output_path, fps=fps, downsample=downsample)
