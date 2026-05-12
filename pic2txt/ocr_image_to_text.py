#!/usr/bin/env python3
"""
单张英文图片 OCR：默认使用 RapidOCR（ONNXRuntime），适合等宽代码/栈轨迹类截图。

可选与参考文本（如 demo_val.txt）比对相似度；默认采用「去空白 + 全角逗号归一」后的
difflib.SequenceMatcher 比值，以弱化行号与空格差异对排版类 OCR 的影响。

用法（在 conda 环境 ocr_env 中）:
  python ocr_image_to_text.py 图片路径 [--reference demo_val.txt] [--output out.txt]
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps
from PIL.Image import UnidentifiedImageError


def _normalize_for_compare(text: str) -> str:
    """弱化空白与标点变体，便于与参考栈文本对齐。"""
    s = text.replace("\uff0c", ",").replace("\u3001", ",").replace("\uff1a", ":")
    s = s.replace("，", ",")
    return re.sub(r"\s+", "", s)


def similarity(ref: str, hyp: str) -> float:
    a = _normalize_for_compare(ref)
    b = _normalize_for_compare(hyp)
    if not a and not b:
        return 1.0
    return float(difflib.SequenceMatcher(None, a, b).ratio())


def _median(xs: list[float]) -> float:
    if not xs:
        return 12.0
    ys = sorted(xs)
    return float(ys[len(ys) // 2])


def _cluster_text_lines(
    items: list[tuple[float, float, str]],
    *,
    y_tol: float,
) -> str:
    """按行聚合同一基线的检测框，按 x 拼接文本。"""
    rows = sorted(items, key=lambda r: (r[0], r[1]))
    merged: list[list[tuple[float, float, str]]] = []
    y_sums: list[list[float]] = []
    for cy, cx, tx in rows:
        if not merged:
            merged.append([(cy, cx, tx)])
            y_sums.append([cy])
            continue
        mean_y = sum(y_sums[-1]) / len(y_sums[-1])
        if abs(cy - mean_y) <= y_tol:
            merged[-1].append((cy, cx, tx))
            y_sums[-1].append(cy)
        else:
            merged.append([(cy, cx, tx)])
            y_sums.append([cy])
    out_lines: list[str] = []
    for parts in merged:
        parts.sort(key=lambda p: p[1])
        out_lines.append("".join(p[2] for p in parts if p[2]))
    return "\n".join(out_lines)


def _rapidocr_items(result: list) -> list[tuple[float, float, str]]:
    items: list[tuple[float, float, str]] = []
    for box, text, _score in result:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        cx = sum(xs) / 4.0
        cy = sum(ys) / 4.0
        t = str(text).strip()
        if t:
            items.append((cy, cx, t))
    return items


def _box_heights(result: list) -> list[float]:
    hs: list[float] = []
    for box, _text, _score in result:
        ys = [p[1] for p in box]
        hs.append(float(max(ys) - min(ys)))
    return hs


def run_rapidocr(image: Image.Image) -> tuple[str, float]:
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    result, _elapsed = engine(np.asarray(image))

    if not result:
        return "", 12.0
    med_h = _median(_box_heights(result))
    y_tol = max(8.0, min(18.0, med_h * 0.55))
    items = _rapidocr_items(result)
    return _cluster_text_lines(items, y_tol=y_tol), med_h


def _load_rgb(path: Path) -> Image.Image:
    im = Image.open(path)
    return ImageOps.exif_transpose(im).convert("RGB")


def _print_unidentified_image_help(path: Path) -> None:
    """Pillow 无法解码时给出文件头线索（常见原因是扩展名与真实格式不符）。"""
    try:
        raw = path.read_bytes()[:64]
    except OSError as e:
        print(f"错误：无法读取文件内容: {e}", file=sys.stderr)
        return
    hex16 = " ".join(f"{b:02x}" for b in raw[:16])
    head_txt = raw[:48].decode("latin-1", errors="replace").replace("\n", "\\n")
    print(
        "错误：Pillow 无法将该文件识别为支持的位图格式（常见图片应为 JPEG 以 ff d8 ff 开头，"
        "PNG 以 89 50 4e 47 开头）。\n"
        f"路径: {path}\n"
        f"文件头(前16字节 hex): {hex16}\n"
        f"文件头(ASCII 视角): {head_txt!r}",
        file=sys.stderr,
    )
    if raw.startswith(b"%TSD-Header"):
        print(
            "提示：检测到 “%TSD-Header” 类文件头，这通常不是标准 JPG/PNG，"
            "而是某些软件/会话的专有容器或中间格式；请用来源软件「导出为 PNG/JPEG」"
            "或用能识别该格式的工具先转成真图片后再 OCR。",
            file=sys.stderr,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="英文图片 OCR（RapidOCR ONNX）")
    parser.add_argument("image", type=str, help="输入图片路径")
    parser.add_argument(
        "--reference",
        type=str,
        default="",
        metavar="PATH",
        help="可选：参考文本文件，用于计算相似度（如 demo_val.txt）",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="",
        metavar="PATH",
        help="将识别结果写入该文件（UTF-8）",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="与参考文本比对时的通过阈值（默认 0.9）",
    )
    parser.add_argument(
        "--upscale",
        type=float,
        default=1.0,
        metavar="FACTOR",
        help="识别前将图像长宽放大倍数，弱截图较小时可试 1.5~2.0（默认 1.0）",
    )
    args = parser.parse_args()

    img_path = Path(args.image).expanduser().resolve()
    if not img_path.is_file():
        print(f"错误：找不到图片文件: {img_path}", file=sys.stderr)
        return 1

    try:
        image = _load_rgb(img_path)
    except UnidentifiedImageError:
        _print_unidentified_image_help(img_path)
        return 1
    if args.upscale and args.upscale != 1.0:
        w, h = image.size
        image = image.resize(
            (max(1, int(w * args.upscale)), max(1, int(h * args.upscale))),
            Image.Resampling.LANCZOS,
        )

    text, _med_h = run_rapidocr(image)
    text = text.strip() + ("\n" if text.strip() else "")

    if args.output:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8")
        print(f"已写入: {out_path}")

    sys.stdout.write(text)
    if text and not text.endswith("\n"):
        sys.stdout.write("\n")

    if args.reference.strip():
        ref_path = Path(args.reference).expanduser().resolve()
        if not ref_path.is_file():
            print(f"错误：找不到参考文件: {ref_path}", file=sys.stderr)
            return 1
        ref = ref_path.read_text(encoding="utf-8")
        raw_ratio = float(difflib.SequenceMatcher(None, ref, text).ratio())
        cmp_ratio = similarity(ref, text)
        print(
            f"与参考文本相似度（原始）: {raw_ratio:.4f}\n"
            f"与参考文本相似度（归一后，用于判定）: {cmp_ratio:.4f}\n"
            f"阈值: {args.threshold:.4f}",
            file=sys.stderr,
        )
        if cmp_ratio + 1e-9 < float(args.threshold):
            print("未通过阈值。", file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
