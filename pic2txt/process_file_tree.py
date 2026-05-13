#!/usr/bin/env python3
"""
递归遍历 src_dir 下所有 .png，按 ocr_image_to_text.py 同款流程做 OCR，
将结果写入 dst_dir 中与之相对路径一致的 .txt（自动创建子目录）。

用法:
  python process_file_tree.py /path/to/src -o /path/to/dst
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image
from PIL.Image import UnidentifiedImageError

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from ocr_image_to_text import (  # noqa: E402
    _load_rgb,
    _print_unidentified_image_help,
    run_rapidocr,
)


def iter_png_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() == ".png":
            out.append(p)
    return sorted(out)


def ocr_png_to_text(path: Path, *, upscale: float) -> str:
    image = _load_rgb(path)
    if upscale and upscale != 1.0:
        w, h = image.size
        image = image.resize(
            (max(1, int(w * upscale)), max(1, int(h * upscale))),
            Image.Resampling.LANCZOS,
        )
    text, _med_h = run_rapidocr(image)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description="批量 OCR：目录树下所有 PNG → 镜像 .txt")
    parser.add_argument(
        "src_dir",
        type=str,
        help="输入根目录（递归查找 .png，大小写后缀均视为 png）",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="dst_dir",
        type=str,
        required=True,
        metavar="DST_DIR",
        help="输出根目录（与源相对路径对齐）",
    )
    parser.add_argument(
        "--upscale",
        type=float,
        default=1.0,
        metavar="FACTOR",
        help="识别前缩放倍数（与单张脚本一致；弱图可试 1.5~2.0，默认 1.0）",
    )
    args = parser.parse_args()

    src_root = Path(args.src_dir).expanduser().resolve()
    dst_root = Path(args.dst_dir).expanduser().resolve()

    if not src_root.is_dir():
        print(f"错误：src_dir 不是目录或不存在: {src_root}", file=sys.stderr)
        return 1

    png_files = iter_png_files(src_root)
    if not png_files:
        print(f"未发现 PNG 文件: {src_root}", file=sys.stderr)
        return 0

    ok = 0
    failed = 0
    for png in png_files:
        rel = png.relative_to(src_root)
        out_txt = (dst_root / rel).with_suffix(".txt")
        try:
            text = ocr_png_to_text(png, upscale=float(args.upscale))
            out_txt.parent.mkdir(parents=True, exist_ok=True)
            out_txt.write_text(text, encoding="utf-8")
            print(f"已写入: {out_txt}")
            ok += 1
        except UnidentifiedImageError:
            _print_unidentified_image_help(png)
            print(f"跳过（无法解码）: {png}", file=sys.stderr)
            failed += 1
        except OSError as e:
            print(f"错误：{png} → {out_txt}: {e}", file=sys.stderr)
            failed += 1
        except Exception as e:
            print(f"错误：{png}: {e}", file=sys.stderr)
            failed += 1

    print(f"完成：成功 {ok}，失败 {failed}，共 {len(png_files)} 个 PNG", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
