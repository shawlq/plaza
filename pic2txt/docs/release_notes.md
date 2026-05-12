# Release notes — OCR 批处理（pic2txt）

## 环境

- 使用 Conda 创建环境：`ocr_env`（示例：`conda create -n ocr_env python=3.10 -y`）。
- 激活后安装依赖：`pip install -r requirements.txt`。`requirements.txt` 默认按 **GPU** 解析依赖：
  - **PyTorch**：`--extra-index-url https://download.pytorch.org/whl/cu124`（CUDA 12.4 系列 wheel）。
  - **Paddle**：`paddlepaddle-gpu` + 飞桨源 `.../stable/cu118/`（CUDA 11.8 系列 wheel，与 OCR 脚本常用组合一致）。
- **若你曾按旧版装过 CPU 包**：请先在同一环境中卸载再重装，避免混用两套轮子，例如：  
  `pip uninstall -y torch torchvision torchaudio paddlepaddle paddlepaddle-gpu`  
  然后重新 `pip install -r requirements.txt`；或新建一个 Conda 环境再装一遍最省事。
- **仅 CPU 调试**：可安装 CPU 版 PyTorch / `paddlepaddle`（CPU）并运行脚本时加 `--cpu`；此时不必强行使用本文件中的 GPU 源（可自行改 requirements 或另建 requirements-cpu.txt，当前仓库以 GPU 默认为主）。

## 功能说明

1. **依赖**：通过 `requirements.txt` 安装 TrOCR（基于 `transformers` + GPU 版 `torch`）与 PaddleOCR（`paddlepaddle-gpu`）。
2. **脚本**：`process_by_ocr.py`，在仓库 `pic2txt` 目录下。
3. **命令行参数**（两个入参）：
   - `src_dir`（第 1 个位置参数，**必填**）：存放待识别图片的目录。
   - `mdl`（第 2 个位置参数，**可选**，默认 `trocr`）：`trocr` 或 `paddleocr`。
4. **输出目录**：在 `src_dir` 下创建 `export_{模型名}/`（例如 `export_trocr/`、`export_paddleocr/`）。
5. **处理逻辑**：遍历 `src_dir` **下一层**中的图片文件（常见后缀：png、jpg、jpeg、bmp、gif、webp、tif/tiff）；子目录中的图片不会递归扫描（因此 `export_trocr/` 等输出目录内的文件不会被再次识别）。对每张图做 OCR，将文本写入 `export_{模型名}/{图片文件名去后缀}.txt`。
6. **网络**：首次 `pip install` 与 TrOCR 拉取 Hugging Face 权重需外网；若中断可重复执行同一 pip 命令。大包下载失败时可换时段或配置 PyPI/代理镜像后重试。
7. **TrOCR 默认模型**：`microsoft/trocr-base-printed`（印刷体）；首次运行会从 Hugging Face 下载权重。
8. **PaddleOCR**：默认启用角度分类、`lang='ch'`（中英文场景）；可按需改脚本内参数。

## 原始需求对照（验收清单）

1. 在 Conda 环境 `ocr_env` 中通过 pip 安装 TrOCR（Transformers 路线）与 PaddleOCR。
2. 在 `pic2txt` 目录提供脚本 `process_by_ocr.py`。
3. 脚本入参：`src_dir` 必填；`mdl` 为第二个位置参数，默认 `trocr`，可写 `paddleocr`。
4. 在 `src_dir` 下自动创建 `export_{模型名}/` 目录。
5. 遍历 `src_dir` 下（本实现为**非递归**，仅顶层）图片，识别结果写入 `export_{模型名}/{图片主文件名}.txt`（与源图主名一致、扩展名为 `.txt`）。
6. 所有 Python 依赖写入 `requirements.txt`。
7. 本文档 `docs/release_notes.md` 记录上述约定与使用说明。

## 使用示例

```bash
conda activate ocr_env
cd /path/to/pic2txt
python process_by_ocr.py /path/to/images
python process_by_ocr.py /path/to/images paddleocr
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `requirements.txt` | Python 依赖 |
| `process_by_ocr.py` | 批处理入口脚本 |
| `docs/release_notes.md` | 本说明（需求与发布说明） |
