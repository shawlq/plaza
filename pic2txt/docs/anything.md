# pic2txt — OCR 选型、校验与排错纪要

本文档整理与 `pic2txt` 单图 OCR 脚本相关的背景、模型对比方式、与 `demo_val.txt` 的相似度定义，以及「伪 JPG」类问题的排查结论，便于后续查阅与交接。

---

## 1. 仓库内相关文件

| 路径 | 说明 |
|------|------|
| `ocr_image_to_text.py` | 单张英文图片 OCR；默认 **RapidOCR（ONNXRuntime）**；可选 `--reference` 与 `demo_val.txt` 比对。 |
| `process_by_ocr.py` | 目录批处理：支持 **TrOCR** / **PaddleOCR**（与 `ocr_image_to_text.py` 路线不同）。 |
| `demo_val.txt` | 英文栈轨迹参考文本，用于验证识别质量。 |
| `requirements.txt` | 含 PyTorch、Paddle、以及 RapidOCR 所需 `onnxruntime`、`rapidocr-onnxruntime` 等。 |
| `docs/release_notes.md` | 以 `process_by_ocr.py` 为主的环境与发布说明。 |

---

## 2. 最终选用的 OCR 模型

**`ocr_image_to_text.py` 固定使用：`rapidocr_onnxruntime.RapidOCR`（RapidOCR + ONNXRuntime 推理）。**

- 典型流程仍为 **文字检测 + 文字识别** 两阶段，与 PaddleOCR 同类。
- 默认 **CPU 可跑**，不强制依赖 CUDA/cuDNN（与部分 Paddle GPU 环境问题解耦）。

---

## 3. 选型时对比过哪些方案、结论如何

在同一张（或同类）栈轨迹截图、同一份 `demo_val.txt` 下做过离线对比，结论摘要如下。

### 3.1 PaddleOCR（英文）

- 对密集 `::`、`<>、`、`const&` 等符号 **误拆、误插空格** 较多。
- 行聚类后整段与参考的 **原始** 序列相似度偏低。
- 降低检测阈值时偶能补全个别长行片段，但与 Rapid 结果 **简单合并** 易产生重复/冲突，整体分数变差。

### 3.2 TrOCR（如 `microsoft/trocr-base-printed`）

- 更偏向 **整段印刷体段落**；将 **整屏多行等宽栈** 一次性送入时，输出与参考 **严重不符**。
- 若要用 TrOCR 做好此类图，一般需要 **先切行/切块** 再识别，脚本与调参成本明显上升。

### 3.3 EasyOCR、Tesseract

- 在同类合成/截图上 **断行、碎片或符号错误** 仍偏多，未作为单脚本默认方案。

### 3.4 RapidOCR（ONNX）

- 检测框按行聚类、按 `x` 拼接后，与 `demo_val.txt` 在 **归一化相似度** 下可稳定超过 **0.9** 的验收目标（见下节）。
- 依赖相对轻，适合「单脚本 + 本地 CPU」场景。

---

## 4. 与 `demo_val.txt` 的相似度如何定义

脚本在传入 `--reference`（例如 `demo_val.txt`）时会计算 **两种** 相似度，并打印到 **stderr**。

### 4.1 原始相似度（`raw_ratio`）

- 对 **参考全文** 与 **OCR 输出全文** 直接调用：

  `difflib.SequenceMatcher(None, ref, text).ratio()`

- **换行、多空格、行号与正文间距** 均计入差异，对「OCR 常吃掉行首空格/行号」的排版 **偏严**，主要作 **诊断参考**。

### 4.2 归一后相似度（`cmp_ratio`，默认用于是否通过阈值）

1. 对 `ref` 与 `text` **分别**做 `_normalize_for_compare`：
   - 全角逗号、顿号、全角冒号等 → 半角 `,` `:`（含常见全角/中文标点变体）。
   - `re.sub(r"\s+", "", s)`：**删除所有空白字符**（空格、换行、制表等）。
2. 再对归一后的两段字符串做 `SequenceMatcher.ratio()`，得到 **0～1** 的标量。
3. 与 `--threshold`（默认 **0.9**）比较：`cmp_ratio + 1e-9 < threshold` 则 **退出码 2**（未通过）。

**设计意图：** `demo_val.txt` 中带 `0   MyMain` 这类 **行号 + 多空格** 排版；OCR 常得到 `MyMain`、`1paddle_...` 等 **空白分布不同** 的串。归一后更侧重 **非空白字符序列是否一致**，避免把「排版差异」当成「内容错误」，因此 **默认用 `cmp_ratio` 做 90% 门禁**。

### 4.3 代码位置（便于对照）

- 归一与 `similarity()`：`ocr_image_to_text.py` 中 `_normalize_for_compare`、`similarity`。
- 打印与判定：`main()` 内读取 `reference` 后的 `raw_ratio` / `cmp_ratio` 与 `threshold` 分支。

---

## 5. 脚本行为与命令示例

```bash
conda run -n ocr_env python ocr_image_to_text.py 图片路径 \
  [--reference demo_val.txt] \
  [-o 输出.txt] \
  [--threshold 0.9] \
  [--upscale 1.0]
```

- 识别结果写入 **stdout**；若指定 `-o` 则同时写入文件。
- **退出码**：`0` 成功；`1` 输入/参考路径等错误；`2` 参考比对未达阈值。
- **`--upscale`**：弱截图较小时可试 `1.5`～`2.0` 放大后再识别。

---

## 6. 「JPG 无法识别」与 `UnidentifiedImageError`

### 6.1 常见误解

Pillow **支持标准 JPEG**（`.jpg` / `.jpeg`）。若报错 `PIL.UnidentifiedImageError: cannot identify image file`，多数不是「不支持 jpg」，而是 **文件内容不是 Pillow 能识别的位图格式**。

### 6.2 典型案例：`%TSD-Header-###%`

曾遇到扩展名为 `.jpg`，但文件头为 ASCII **`%TSD-Header-###%`**（十六进制以 `25 54 53 44 ...` 开头），而 **真 JPEG** 应以 **`ff d8 ff`** 开头。`file` 命令常显示为 `data`。

此类多为 **某软件/会话的专有容器或中间格式**，被误存或误命名为 `.jpg`。处理办法：

- 在 **生成该文件的软件** 中使用 **「导出为 PNG / JPEG」** 得到标准图片；或  
- 使用 **能识别该容器格式** 的工具先转为真图片，再跑 OCR。

### 6.3 脚本改进

`ocr_image_to_text.py` 在捕获 `UnidentifiedImageError` 时会：

- 打印文件头 hex 与可读片段；  
- 若检测到 `%TSD-Header` 前缀，提示 **非标准 JPG/PNG**，需先转换格式。

---

## 7. 与 `process_by_ocr.py` 的分工

| 维度 | `ocr_image_to_text.py` | `process_by_ocr.py` |
|------|------------------------|----------------------|
| 输入 | 单张图片路径 | 图片目录 |
| 默认引擎 | RapidOCR（ONNX） | TrOCR（默认）或 PaddleOCR |
| GPU | 不强制 | 默认倾向 GPU（可用 `--cpu`） |
| 参考比对 | 可选 `--reference` + 归一相似度 | 无内置与 `demo_val.txt` 比对 |

二者互补：批量、多模型实验可走 `process_by_ocr.py`；单图、轻依赖、与参考文本验收可走 `ocr_image_to_text.py`。

---

## 8. 修订历史（文档层面）

- 整理上述选型理由、相似度定义、`demo_val.txt` 验收逻辑、伪 JPG / TSD 头问题与脚本行为，汇总为本文件 `docs/anything.md`。

若后续更改相似度算法或默认 OCR 引擎，请同步更新本节与 `ocr_image_to_text.py` 内 docstring。
