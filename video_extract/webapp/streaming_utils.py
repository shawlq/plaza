"""Helpers for HLS playlist generation and cache bookkeeping."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HLS_PLAYLIST_NAME = "playlist.m3u8"
HLS_STATUS_NAME = "status.json"
HLS_LOG_NAME = "ffmpeg.log"

_HLS_BUILD_LOCK = threading.Lock()
_HLS_BUILDERS: dict[str, threading.Thread] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ffmpeg_executable() -> str:
    executable = os.environ.get("VIDEO_EXTRACT_FFMPEG_BIN", "ffmpeg").strip()
    return executable or "ffmpeg"


def ffmpeg_available() -> bool:
    return shutil.which(ffmpeg_executable()) is not None


def video_cache_key(video_path: Path) -> str:
    stat = video_path.stat()
    raw = f"{video_path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def hls_cache_dir(cache_root: Path, video_path: Path) -> Path:
    safe_stem = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in video_path.stem)
    safe_stem = safe_stem.strip("._") or "video"
    return cache_root / f"{safe_stem}-{video_cache_key(video_path)}"


def hls_playlist_path(cache_root: Path, video_path: Path) -> Path:
    return hls_cache_dir(cache_root, video_path) / HLS_PLAYLIST_NAME


def hls_status_path(cache_root: Path, video_path: Path) -> Path:
    return hls_cache_dir(cache_root, video_path) / HLS_STATUS_NAME


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def _failed_status_payload(video_path: Path, output_dir: Path, error: str) -> dict[str, Any]:
    return {
        "state": "failed",
        "error": error,
        "updated_at": _utc_now(),
        "source_name": video_path.name,
        "cache_dir": str(output_dir),
    }


def _read_status(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return {"state": "failed", "error": f"HLS 状态文件损坏: {path.name}"}


def read_hls_status(cache_root: Path, video_path: Path) -> dict[str, Any]:
    playlist_path = hls_playlist_path(cache_root, video_path)
    status_path = hls_status_path(cache_root, video_path)
    status = _read_status(status_path) or {}
    state = status.get("state")
    if playlist_path.exists() and state == "ready":
        return {
            **status,
            "state": "ready",
            "ready": True,
            "playlist_path": str(playlist_path),
        }
    if state == "preparing":
        return {
            **status,
            "state": "preparing",
            "ready": False,
            "playlist_path": str(playlist_path),
        }
    if state == "failed":
        return {
            **status,
            "state": "failed",
            "ready": False,
            "playlist_path": str(playlist_path),
        }
    return {
        **status,
        "state": "missing",
        "ready": False,
        "playlist_path": str(playlist_path),
    }


def build_ffmpeg_hls_command(
    input_path: Path,
    output_dir: Path,
    fps: float,
    segment_seconds: int,
) -> list[str]:
    rounded_fps = max(1, int(round(fps))) if fps > 0 else 25
    keyframe_interval = max(12, rounded_fps)
    executable = ffmpeg_executable()
    return [
        executable,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-sn",
        "-dn",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-g",
        str(keyframe_interval),
        "-keyint_min",
        str(keyframe_interval),
        "-sc_threshold",
        "0",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-f",
        "hls",
        "-hls_time",
        str(max(1, segment_seconds)),
        "-hls_playlist_type",
        "vod",
        "-hls_flags",
        "independent_segments+temp_file",
        "-hls_segment_filename",
        str(output_dir / "segment-%05d.ts"),
        str(output_dir / HLS_PLAYLIST_NAME),
    ]


def _build_hls_playlist(
    cache_root: Path,
    video_path: Path,
    fps: float,
    segment_seconds: int,
) -> None:
    output_dir = hls_cache_dir(cache_root, video_path)
    status_path = hls_status_path(cache_root, video_path)
    playlist_path = output_dir / HLS_PLAYLIST_NAME
    log_path = output_dir / HLS_LOG_NAME
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_json_atomic(
        status_path,
        {
            "state": "preparing",
            "error": None,
            "updated_at": _utc_now(),
            "source_name": video_path.name,
            "cache_dir": str(output_dir),
        },
    )

    command = build_ffmpeg_hls_command(video_path, output_dir, fps=fps, segment_seconds=segment_seconds)
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        _write_json_atomic(
            status_path,
            _failed_status_payload(
                video_path,
                output_dir,
                f"HLS 不可用：未找到 ffmpeg，可安装 ffmpeg 或设置 VIDEO_EXTRACT_FFMPEG_BIN 指向可执行文件。",
            ),
        )
        return
    except Exception as exc:
        _write_json_atomic(
            status_path,
            _failed_status_payload(video_path, output_dir, f"HLS 生成异常: {exc}"),
        )
        return
    log_text = (result.stdout or "") + (result.stderr or "")
    if log_text:
        log_path.write_text(log_text, encoding="utf-8")
    if result.returncode != 0 or not playlist_path.exists():
        _write_json_atomic(
            status_path,
            _failed_status_payload(
                video_path,
                output_dir,
                (result.stderr or result.stdout or "ffmpeg 未生成 HLS 播放列表").strip(),
            ),
        )
        return

    _write_json_atomic(
        status_path,
        {
            "state": "ready",
            "error": None,
            "updated_at": _utc_now(),
            "source_name": video_path.name,
            "cache_dir": str(output_dir),
        },
    )


def ensure_hls_generation(
    cache_root: Path,
    video_path: Path,
    fps: float,
    segment_seconds: int,
    *,
    start_build: bool,
) -> dict[str, Any]:
    status = read_hls_status(cache_root, video_path)
    if status["state"] in {"ready", "failed"} or not start_build:
        return status

    if not ffmpeg_available():
        output_dir = hls_cache_dir(cache_root, video_path)
        status_path = hls_status_path(cache_root, video_path)
        _write_json_atomic(
            status_path,
            _failed_status_payload(
                video_path,
                output_dir,
                "HLS 不可用：未找到 ffmpeg，可安装 ffmpeg 或设置 VIDEO_EXTRACT_FFMPEG_BIN 指向可执行文件。",
            ),
        )
        return read_hls_status(cache_root, video_path)

    key = str(hls_playlist_path(cache_root, video_path))
    with _HLS_BUILD_LOCK:
        thread = _HLS_BUILDERS.get(key)
        if thread and thread.is_alive():
            return read_hls_status(cache_root, video_path)

        thread = threading.Thread(
            target=_build_hls_playlist,
            args=(cache_root, video_path, fps, segment_seconds),
            name=f"hls-build-{video_cache_key(video_path)}",
            daemon=True,
        )
        _HLS_BUILDERS[key] = thread
        thread.start()
    return read_hls_status(cache_root, video_path)
