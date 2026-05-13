"""Check whether the external libcimbar encoder is available.

libcimbar is not distributed as a Python package, so ``pip install -r
requirements.txt`` cannot install ``cimbar.exe``. This helper gives a clear
post-install check and points Windows users at the next setup step.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Sequence


LATEST_RELEASE_API = "https://api.github.com/repos/sz3/libcimbar/releases/latest"


def local_binary_candidates(tool_dir: Path) -> list[Path]:
    return [
        tool_dir / "bin" / "cimbar.exe",
        tool_dir / "bin" / "cimbar",
        tool_dir / "cimbar.exe",
        tool_dir / "cimbar",
    ]


def find_cimbar(tool_dir: Path) -> Path | None:
    env_path = os.environ.get("CIMBAR_BIN")
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file():
            return path

    for candidate in local_binary_candidates(tool_dir):
        if candidate.is_file():
            return candidate

    for command in ("cimbar.exe", "cimbar"):
        found = shutil.which(command)
        if found:
            return Path(found)

    return None


def latest_web_encoder_url() -> str:
    with urllib.request.urlopen(LATEST_RELEASE_API, timeout=30) as response:
        release = json.loads(response.read().decode("utf-8"))
    for asset in release.get("assets", []):
        if asset.get("name") == "cimbar_js.html":
            return asset["browser_download_url"]
    raise RuntimeError("Cannot find cimbar_js.html in the latest libcimbar release.")


def download_web_encoder(tool_dir: Path) -> Path:
    target_dir = tool_dir / "vendor"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "cimbar_js.html"
    url = latest_web_encoder_url()
    print(f"Downloading official web encoder: {url}")
    with urllib.request.urlopen(url, timeout=60) as response:
        target.write_bytes(response.read())
    return target


def print_missing_message() -> None:
    print(
        """
没有找到 cimbar.exe。

原因：
  python -m pip install -r requirements.txt 只安装 Python 依赖。
  libcimbar 官方目前没有 pip 包，也没有官方 Windows cimbar.exe release；
  官方 release 主要提供 cimbar_js.html / wasm / asm.js Web 编码器。

如果要继续使用本仓库的批量 PNG 自动导出脚本，你需要先准备命令行版 cimbar：

  方案 A：自己构建 libcimbar，然后把生成的 cimbar.exe 放到：
    cimbar_tool\\bin\\cimbar.exe

  方案 B：把已有 cimbar.exe 加入 PATH，或设置：
    set CIMBAR_BIN=C:\\path\\to\\cimbar.exe

  方案 C：运行脚本时显式指定：
    python text_to_cimbar_png.py C:\\path\\to\\texts --cimbar-bin C:\\path\\to\\cimbar.exe

如果你只是想使用官方浏览器版编码器，可执行：
    python check_cimbar_setup.py --download-web-encoder
然后打开 cimbar_tool\\vendor\\cimbar_js.html 手动选择文件编码。
注意：浏览器版是手动工具，不等价于本仓库的目录批量自动导出脚本。
""".strip()
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check libcimbar command line encoder setup.")
    parser.add_argument(
        "--download-web-encoder",
        action="store_true",
        help="Download official cimbar_js.html for manual browser-based encoding.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    tool_dir = Path(__file__).resolve().parent

    cimbar = find_cimbar(tool_dir)
    if cimbar:
        print(f"Found cimbar executable: {cimbar}")
        return 0

    print_missing_message()
    if args.download_web_encoder:
        try:
            target = download_web_encoder(tool_dir)
        except Exception as exc:  # noqa: BLE001 - CLI helper should print actionable error.
            print(f"下载官方 Web 编码器失败：{exc}", file=sys.stderr)
            return 1
        print(f"已下载：{target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
