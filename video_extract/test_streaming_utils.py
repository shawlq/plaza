from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from webapp.streaming_utils import (
    HLS_PLAYLIST_NAME,
    build_ffmpeg_hls_command,
    hls_cache_dir,
    hls_status_path,
    read_hls_status,
    video_cache_key,
)


class StreamingUtilsTests(unittest.TestCase):
    def test_video_cache_key_is_stable_length(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = Path(temp_dir) / "demo.mp4"
            video_path.write_bytes(b"demo-video")
            self.assertEqual(len(video_cache_key(video_path)), 16)
            self.assertEqual(video_cache_key(video_path), video_cache_key(video_path))

    def test_hls_cache_dir_sanitizes_video_stem(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            video_path = Path(temp_dir) / "demo clip(1).mp4"
            video_path.write_bytes(b"x")
            cache_dir = hls_cache_dir(cache_root, video_path)
            self.assertTrue(cache_dir.name.startswith("demo_clip_1-"))

    def test_build_ffmpeg_hls_command_contains_hls_flags(self) -> None:
        command = build_ffmpeg_hls_command(Path("/tmp/input.mp4"), Path("/tmp/out"), fps=29.97, segment_seconds=2)
        joined = " ".join(command)
        self.assertIn("-f hls", joined)
        self.assertIn("-hls_time 2", joined)
        self.assertIn("-c:v libx264", joined)
        self.assertIn("-c:a aac", joined)
        self.assertIn("/tmp/out/segment-%05d.ts", joined)
        self.assertTrue(command[-1].endswith(f"/{HLS_PLAYLIST_NAME}"))

    def test_read_hls_status_defaults_to_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            video_path = Path(temp_dir) / "demo.mp4"
            video_path.write_bytes(b"x")
            status = read_hls_status(cache_root, video_path)
            self.assertEqual(status["state"], "missing")
            self.assertFalse(status["ready"])

    def test_read_hls_status_requires_playlist_for_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            video_path = Path(temp_dir) / "demo.mp4"
            video_path.write_bytes(b"x")
            status_path = hls_status_path(cache_root, video_path)
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(
                json.dumps({"state": "ready", "updated_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            status = read_hls_status(cache_root, video_path)
            self.assertEqual(status["state"], "missing")
            self.assertFalse(status["ready"])

    def test_read_hls_status_returns_ready_when_playlist_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir) / "cache"
            video_path = Path(temp_dir) / "demo.mp4"
            video_path.write_bytes(b"x")
            cache_dir = hls_cache_dir(cache_root, video_path)
            cache_dir.mkdir(parents=True, exist_ok=True)
            (cache_dir / HLS_PLAYLIST_NAME).write_text("#EXTM3U\n", encoding="utf-8")
            hls_status_path(cache_root, video_path).write_text(
                json.dumps({"state": "ready", "updated_at": "2026-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            status = read_hls_status(cache_root, video_path)
            self.assertEqual(status["state"], "ready")
            self.assertTrue(status["ready"])


if __name__ == "__main__":
    unittest.main()
