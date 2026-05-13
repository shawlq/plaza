"""Smoke test for the cimbar text encoder wrapper.

The test uses a tiny fake cimbar executable so it can run on machines that do
not have libcimbar installed. It verifies our Python wrapper's file discovery,
output layout, subprocess invocation, and manifest generation.
"""

from __future__ import annotations

import json
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


def write_fake_cimbar(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import pathlib",
                "import sys",
                "",
                "prefix = pathlib.Path(sys.argv[sys.argv.index('-o') + 1])",
                "prefix.parent.mkdir(parents=True, exist_ok=True)",
                "(prefix.with_name(prefix.name + '_0.png')).write_bytes(b'PNG')",
                "",
            ]
        ),
        encoding="utf-8",
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def main() -> int:
    tool_dir = Path(__file__).resolve().parent
    encoder = tool_dir / "text_to_cimbar_png.py"

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        src_dir = root / "texts"
        src_dir.mkdir()
        (src_dir / "hello.txt").write_text("hello cimbar", encoding="utf-8")
        (src_dir / "ignore.bin").write_text("not a text extension", encoding="utf-8")
        nested_dir = src_dir / "nested"
        nested_dir.mkdir()
        (nested_dir / "note.md").write_text("# nested", encoding="utf-8")

        fake_cimbar = root / "cimbar"
        write_fake_cimbar(fake_cimbar)

        output_dir = root / "out"
        command = [
            sys.executable,
            str(encoder),
            str(src_dir),
            "--output-dir",
            str(output_dir),
            "--recursive",
            "--cimbar-bin",
            str(fake_cimbar),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, end="", file=sys.stderr)
        if completed.returncode != 0:
            return completed.returncode

        expected_pngs = [
            output_dir / "hello_txt" / "hello_0.png",
            output_dir / "nested" / "note_md" / "note_0.png",
        ]
        for png_path in expected_pngs:
            if not png_path.is_file():
                print(f"Missing expected PNG: {png_path}", file=sys.stderr)
                return 1

        unexpected_png = output_dir / "ignore_bin" / "ignore_0.png"
        if unexpected_png.exists():
            print(f"Unexpected PNG for ignored extension: {unexpected_png}", file=sys.stderr)
            return 1

        manifest_path = output_dir / "manifest.json"
        if not manifest_path.is_file():
            print(f"Missing manifest: {manifest_path}", file=sys.stderr)
            return 1

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if len(manifest.get("items", [])) != 2:
            print("Manifest should contain exactly 2 encoded items.", file=sys.stderr)
            return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
