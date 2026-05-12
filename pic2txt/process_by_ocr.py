#!/usr/bin/env python3
"""
遍历图片目录，使用 TrOCR 或 PaddleOCR 识别文字，结果写入 export_{模型名}/ 下同名 .txt。
默认使用 GPU；无可用 GPU 时退出（可用 --cpu 强制走 CPU）。
PaddleOCR：若 GPU 可见但 cuDNN 不可用，会报错退出（不再自动改 CPU，因部分环境 CPU 版会触发 Illegal instruction）。
TrOCR 默认从 Hugging Face 拉取 microsoft/trocr-base-printed；无外网时可 --trocr-model 本地目录
或 --local-files-only（依赖已有缓存），详见 --help。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES


def _iter_images(src_dir: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(src_dir.iterdir()):
        if not _is_image_file(p):
            continue
        out.append(p)
    return out


def _torch_has_cuda() -> bool:
    import torch

    return torch.cuda.is_available()


def _torch_device_line(use_gpu: bool) -> str:
    import torch

    if not use_gpu:
        return "设备: CPU（由 --cpu 指定）"
    if torch.cuda.is_available():
        return f"设备: GPU（PyTorch / CUDA，{torch.cuda.get_device_name(0)}）"
    return "设备: CPU（未检测到 CUDA）"


def _paddle_has_cuda() -> bool:
    import paddle

    if not paddle.device.is_compiled_with_cuda():
        return False
    try:
        return int(paddle.device.cuda.device_count()) > 0
    except Exception:
        return False


def _paddle_device_line(use_gpu: bool) -> str:
    import paddle

    if not use_gpu:
        return "设备: CPU（由 --cpu 指定）"
    if _paddle_has_cuda():
        n = int(paddle.device.cuda.device_count())
        return f"设备: GPU（PaddlePaddle / CUDA，可见 GPU 数: {n}）"
    return "设备: CPU（Paddle 未带 CUDA 或未检测到 GPU）"


def _ensure_accelerator(mdl: str, use_gpu: bool) -> int:
    """默认要求 GPU；不满足则返回非 0。"""
    if not use_gpu:
        return 0
    if mdl == "trocr":
        if not _torch_has_cuda():
            print(
                "错误：默认使用 GPU，但未检测到可用 CUDA（torch.cuda.is_available() 为 False）。",
                file=sys.stderr,
            )
            print("请安装 GPU 版 PyTorch 与驱动，或追加参数 --cpu 使用 CPU。", file=sys.stderr)
            return 1
        return 0
    if not _paddle_has_cuda():
        print(
            "错误：默认使用 GPU，但 PaddlePaddle 未以 CUDA 编译或未检测到 GPU。",
            file=sys.stderr,
        )
        print("请安装 GPU 版 paddlepaddle 与驱动，或追加参数 --cpu 使用 CPU。", file=sys.stderr)
        return 1
    return 0


def _print_startup(mdl: str, use_gpu: bool, export_dir: Path) -> None:
    print("======== OCR 批处理 ========")
    print(f"模型: {mdl}")
    if mdl == "trocr":
        print(_torch_device_line(use_gpu))
    else:
        print(_paddle_device_line(use_gpu))
    print(f"输出目录: {export_dir}")
    print("============================")


def _trocr_load_kwargs(model_name_or_path: str, *, local_files_only: bool) -> tuple[str, bool]:
    """返回 (传给 from_pretrained 的路径, local_files_only)。本地目录不强制联网。"""
    p = Path(model_name_or_path)
    if p.is_dir():
        return str(p.resolve()), True
    return model_name_or_path, local_files_only


def _run_trocr(
    image_paths: list[Path],
    export_dir: Path,
    *,
    use_gpu: bool,
    model_name_or_path: str,
    local_files_only: bool,
) -> int:
    import torch
    from PIL import Image, UnidentifiedImageError
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    device = "cuda" if use_gpu else "cpu"
    load_path, lfo = _trocr_load_kwargs(model_name_or_path, local_files_only=local_files_only)
    try:
        processor = TrOCRProcessor.from_pretrained(load_path, local_files_only=lfo)
        model = VisionEncoderDecoderModel.from_pretrained(load_path, local_files_only=lfo).to(
            device
        )
    except OSError as e:
        print(
            "错误：无法加载 TrOCR 模型（常见原因：无外网、Hugging Face 不可达、本地无缓存）。\n"
            "可选处理方式：\n"
            "  1) 在有网络的机器用 huggingface-cli download 下载整个仓库，拷贝到本机后：\n"
            "     python process_by_ocr.py 图片目录 trocr --trocr-model /path/to/trocr-folder\n"
            "  2) 若本机 ~/.cache/huggingface 已有完整缓存，可加：--local-files-only\n"
            "  3) 使用镜像（示例）：export HF_ENDPOINT=https://hf-mirror.com\n"
            f"原始异常: {e}",
            file=sys.stderr,
        )
        return 1
    model.eval()

    export_dir.mkdir(parents=True, exist_ok=True)
    skipped = 0

    for img_path in image_paths:
        txt_path = export_dir / f"{img_path.stem}.txt"
        print(f"[trocr][开始] {img_path.name}", flush=True)
        try:
            image = Image.open(img_path).convert("RGB")
        except (UnidentifiedImageError, OSError) as e:
            skipped += 1
            print(
                f"[trocr][跳过] {img_path.name}: 无法作为图片打开（{e}）。"
                " 常见原因：扩展名是图片但实际不是图像数据（例如其它软件的容器/临时文件）、或文件损坏。",
                file=sys.stderr,
                flush=True,
            )
            continue
        pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
        with torch.inference_mode():
            # 显式指定 max_new_tokens，避免 transformers 使用默认 max_length=21 的告警与过早截断
            generated_ids = model.generate(pixel_values, max_new_tokens=512)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        txt_path.write_text(text.strip() + "\n", encoding="utf-8")
        print(f"[trocr][完成] {img_path.name} -> {txt_path.name}", flush=True)
    if skipped:
        print(f"[trocr] 共跳过 {skipped} 个无法解码的文件，其余已处理。", flush=True)
    return 0


def _paddleocr_cudnn_runtime_error(exc: BaseException) -> bool:
    """Paddle 已编译 CUDA 但运行时找不到 cuDNN 动态库时常见此类报错。"""
    msg = str(exc).lower()
    return "cudnn" in msg or "cudnn_dso_handle" in msg


def _run_paddleocr(image_paths: list[Path], export_dir: Path, *, use_gpu: bool) -> int:
    """返回 0 成功；1 表示 GPU 因 cuDNN 不可用而失败（已打印说明，不再静默改跑 CPU）。"""
    from paddleocr import PaddleOCR

    ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False, use_gpu=use_gpu)
    export_dir.mkdir(parents=True, exist_ok=True)

    for img_path in image_paths:
        txt_path = export_dir / f"{img_path.stem}.txt"
        print(f"[paddleocr][开始] {img_path.name}", flush=True)
        try:
            result = ocr.ocr(str(img_path), cls=True)
        except RuntimeError as e:
            if use_gpu and _paddleocr_cudnn_runtime_error(e):
                print(
                    "错误：Paddle GPU 推理需要系统能加载与 CUDA 版本匹配的 cuDNN 动态库，当前加载失败。\n"
                    "处理办法（任选其一）：\n"
                    "  1) 安装与当前 paddlepaddle-gpu / CUDA 对应的 cuDNN，并确保其 lib 在 LD_LIBRARY_PATH（或 ldconfig）中；\n"
                    "  2) 若必须用 CPU：加参数 --cpu（注意：若仍出现 Illegal instruction / SIGILL，说明当前安装的 Paddle\n"
                    "     预编译包使用了本机 CPU 不支持的指令集，需换官方提供的其它 wheel/conda 包或改用 trocr）。\n"
                    f"原始异常: {e}",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            raise
        lines: list[str] = []
        if result and result[0]:
            for line in result[0]:
                if line and len(line) >= 2:
                    text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                    lines.append(str(text).strip())
        txt_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        print(f"[paddleocr][完成] {img_path.name} -> {txt_path.name}", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="图片目录 OCR：TrOCR 或 PaddleOCR，结果写入 export_{模型名}/。用法：process_by_ocr.py src_dir [mdl] [--cpu]"
    )
    parser.add_argument(
        "src_dir",
        type=str,
        help="图片所在目录（必填）",
    )
    parser.add_argument(
        "mdl",
        nargs="?",
        default="trocr",
        choices=("trocr", "paddleocr"),
        help="模型：trocr（默认）或 paddleocr",
    )
    parser.add_argument(
        "--cpu",
        action="store_true",
        help="强制使用 CPU（默认要求 GPU；无 GPU 或不想用 GPU 时加此参数；Paddle 无 cuDNN 时也可避免先尝试 GPU）",
    )
    parser.add_argument(
        "--trocr-model",
        type=str,
        default="microsoft/trocr-base-printed",
        metavar="PATH_OR_ID",
        help="TrOCR：Hugging Face 模型 ID 或已下载的本地目录（含 config、权重与 processor 文件）",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="TrOCR：仅从 Hugging Face 本地缓存读取，不发起网络请求（需已完整缓存）",
    )
    args = parser.parse_args()

    src_dir = Path(args.src_dir).resolve()
    if not src_dir.is_dir():
        print(f"错误：目录不存在或不是文件夹: {src_dir}", file=sys.stderr)
        return 1

    mdl = args.mdl.lower().strip()
    use_gpu = not args.cpu
    export_dir = src_dir / f"export_{mdl}"

    if _ensure_accelerator(mdl, use_gpu) != 0:
        return 1

    _print_startup(mdl, use_gpu, export_dir)

    images = _iter_images(src_dir)
    if not images:
        print(f"未在 {src_dir} 下找到支持的图片文件（后缀 {sorted(IMAGE_SUFFIXES)}）。")
        export_dir.mkdir(parents=True, exist_ok=True)
        return 0

    print(f"待处理图片数: {len(images)}", flush=True)

    if mdl == "trocr":
        if (
            _run_trocr(
                images,
                export_dir,
                use_gpu=use_gpu,
                model_name_or_path=args.trocr_model.strip(),
                local_files_only=args.local_files_only,
            )
            != 0
        ):
            return 1
    else:
        if _run_paddleocr(images, export_dir, use_gpu=use_gpu) != 0:
            return 1

    print(f"全部完成，共 {len(images)} 张，输出目录: {export_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
