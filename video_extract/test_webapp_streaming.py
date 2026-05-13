from __future__ import annotations

import importlib
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class WebAppStreamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.data_root = Path(cls.temp_dir.name) / "data"
        videos_root = cls.data_root / "videos"
        videos_root.mkdir(parents=True, exist_ok=True)
        cls.video_path = videos_root / "sample.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=160x90:rate=24",
                "-t",
                "1",
                "-pix_fmt",
                "yuv420p",
                str(cls.video_path),
            ],
            check=True,
        )

        cls.previous_data_root = os.environ.get("VIDEO_EXTRACT_WEBAPP_DATA")
        os.environ["VIDEO_EXTRACT_WEBAPP_DATA"] = str(cls.data_root)
        app_module = importlib.import_module("webapp.app")
        cls.app_module = importlib.reload(app_module)
        cls.client = TestClient(cls.app_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.previous_data_root is None:
            os.environ.pop("VIDEO_EXTRACT_WEBAPP_DATA", None)
        else:
            os.environ["VIDEO_EXTRACT_WEBAPP_DATA"] = cls.previous_data_root
        cls.temp_dir.cleanup()

    def test_stream_endpoint_supports_range_requests(self) -> None:
        response = self.client.get(
            f"/api/videos/{self.video_path.name}/stream",
            headers={"Range": "bytes=0-15"},
        )
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers["accept-ranges"], "bytes")
        self.assertEqual(response.headers["content-range"].split("/")[0], "bytes 0-15")
        self.assertEqual(len(response.content), 16)

    def test_hls_status_and_assets_eventually_become_ready(self) -> None:
        video_response = self.client.get(f"/api/videos/{self.video_path.name}")
        self.assertEqual(video_response.status_code, 200)
        playback = video_response.json()["video"]["playback"]
        self.assertIn("hls_status_url", playback)
        self.assertIn("hls_manifest_url", playback)

        ready_payload = None
        for _ in range(30):
            status_response = self.client.get(f"/api/videos/{self.video_path.name}/hls/status")
            self.assertEqual(status_response.status_code, 200)
            ready_payload = status_response.json()["playback"]
            if ready_payload["hls_ready"]:
                break
            time.sleep(0.2)

        self.assertIsNotNone(ready_payload)
        self.assertTrue(ready_payload["hls_ready"])

        playlist_response = self.client.get(ready_payload["hls_manifest_url"])
        self.assertEqual(playlist_response.status_code, 200)
        self.assertIn("#EXTM3U", playlist_response.text)
        self.assertIn("max-age=3600", playlist_response.headers["cache-control"])

        segment_name = next(
            line.strip()
            for line in playlist_response.text.splitlines()
            if line.strip() and not line.startswith("#")
        )
        segment_response = self.client.get(f"/api/videos/{self.video_path.name}/hls/{segment_name}")
        self.assertEqual(segment_response.status_code, 200)
        self.assertIn("immutable", segment_response.headers["cache-control"])


if __name__ == "__main__":
    unittest.main()
