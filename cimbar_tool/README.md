# cimbar_tool

面向 Windows 11 的文本目录批量转 cimbar PNG 工具。

本工具使用 Python 脚本扫描目录中的文本文件，并调用 libcimbar 的命令行编码器生成 PNG 帧。libcimbar 的官方编码命令参考：

```bat
cimbar --encode -i inputfile.txt -o outputprefix
```

## 环境准备

建议使用 Python 3.10 或更新版本。

```bat
cd cimbar_tool
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

`requirements.txt` 只覆盖 Python 依赖。当前脚本仅使用 Python 标准库；另需准备 libcimbar 命令行程序：

- 从 <https://github.com/sz3/libcimbar> 按官方说明构建 `cimbar`。
- Windows 11 上请将构建出的 `cimbar.exe` 放到 `cimbar_tool\bin\cimbar.exe`，或加入 `PATH`，或运行脚本时传入 `--cimbar-bin`。
- 也可以设置环境变量 `CIMBAR_BIN=C:\path\to\cimbar.exe`。

## 使用方式

```bat
python text_to_cimbar_png.py C:\path\to\text_dir --cimbar-bin C:\path\to\cimbar.exe
```

默认会在输入目录下生成 `export_cimbar`，每个文本文件独立输出到一个子目录中：

```text
text_dir\
  demo.txt
  export_cimbar\
    demo_txt\
      demo*.png
    manifest.json
```

常用参数：

```bat
python text_to_cimbar_png.py C:\path\to\text_dir -o C:\path\to\out --recursive
python text_to_cimbar_png.py C:\path\to\text_dir --extensions txt,md,json --overwrite
python text_to_cimbar_png.py C:\path\to\text_dir --dry-run
```

也可以使用 Windows 批处理入口：

```bat
run_windows.bat C:\path\to\text_dir --cimbar-bin C:\path\to\cimbar.exe
```

## Smoke 验证

仓库内提供可复用 smoke 测试，不依赖真实 `cimbar.exe`，会用临时假编码器验证 Python 包装脚本的扫描、输出目录、子进程调用和 `manifest.json` 生成逻辑：

```bat
python smoke_test.py
```

## 默认扫描的文本扩展名

`.txt`, `.md`, `.csv`, `.json`, `.jsonl`, `.xml`, `.html`, `.htm`, `.log`, `.ini`, `.cfg`, `.yaml`, `.yml`

可用 `--extensions` 覆盖，例如：

```bat
python text_to_cimbar_png.py C:\path\to\text_dir --extensions txt,md
```

## 说明

- libcimbar 官方项目主要提供 C++ 命令行工具，并非 pip 包；因此 Python 脚本通过子进程调用 `cimbar.exe`。
- 对于较大的输入文件，libcimbar 可能生成多张 PNG。
- 若输出前缀已存在 PNG，脚本默认跳过；需要重新生成时添加 `--overwrite`。
- 处理完成后会写入 `manifest.json`，记录源文件、输出前缀和生成的 PNG 列表。
