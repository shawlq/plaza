import importlib
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


webapp_module = importlib.import_module("video_extract.webapp.app")


class StreamVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = b"0123456789abcdef"
        cls.video_path = webapp_module.VIDEOS_ROOT / "test_stream_video.mp4"
        cls.video_path.parent.mkdir(parents=True, exist_ok=True)
        cls.video_path.write_bytes(cls.payload)
        cls.client = TestClient(webapp_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.video_path.unlink(missing_ok=True)

    def test_stream_full_file_without_range(self) -> None:
        response = self.client.get("/api/videos/test_stream_video.mp4/stream")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("accept-ranges"), "bytes")
        self.assertEqual(response.content, self.payload)
        self.assertIsNone(response.headers.get("content-disposition"))

    def test_stream_explicit_forward_range(self) -> None:
        response = self.client.get(
            "/api/videos/test_stream_video.mp4/stream",
            headers={"Range": "bytes=4-9"},
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers.get("content-range"), "bytes 4-9/16")
        self.assertEqual(response.content, self.payload[4:10])

    def test_stream_suffix_range(self) -> None:
        response = self.client.get(
            "/api/videos/test_stream_video.mp4/stream",
            headers={"Range": "bytes=-4"},
        )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.headers.get("content-range"), "bytes 12-15/16")
        self.assertEqual(response.content, self.payload[-4:])


if __name__ == "__main__":
    unittest.main()
