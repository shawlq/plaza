# Release Notes

## 0513 cimbar_tool

1. 在仓库中新增 `cimbar_tool` 目录，并在其中生成文本目录批量转 cimbar PNG 的工具代码。
2. 支持在 Windows 11 环境中使用 Python 脚本把某个目录下的文本文件转换为 cimbar PNG 图片输出：
   - 入口脚本：`cimbar_tool/text_to_cimbar_png.py`
   - Windows 启动脚本：`cimbar_tool/run_windows.bat`
   - 默认输出目录：输入目录下的 `export_cimbar/`
   - 支持 `--output-dir`、`--cimbar-bin`、`--recursive`、`--extensions`、`--overwrite`、`--keep-going`、`--dry-run` 等参数。
3. cimbar 的库依赖和使用方法参考 <https://github.com/sz3/libcimbar>：
   - Python 脚本调用 libcimbar 命令行编码器。
   - 对单个文本文件的底层编码命令为 `cimbar --encode -i inputfile.txt -o outputprefix`。
   - Windows 11 上需要提前准备 `cimbar.exe`，可通过 `--cimbar-bin` 指定、放入 `cimbar_tool\bin\cimbar.exe`、加入 `PATH`，或设置 `CIMBAR_BIN` 环境变量。
4. 在 `cimbar_tool/requirements.txt` 中记录工具依赖，便于执行 `python -m pip install -r requirements.txt`：
   - 当前 Python 脚本仅使用标准库，因此没有第三方 pip 依赖。
   - libcimbar 是外部命令行程序依赖，不是 pip 包，需要按官方说明构建或安装。

## 使用示例

```bat
cd cimbar_tool
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python text_to_cimbar_png.py C:\path\to\text_dir --cimbar-bin C:\path\to\cimbar.exe
```

或：

```bat
cd cimbar_tool
run_windows.bat C:\path\to\text_dir --cimbar-bin C:\path\to\cimbar.exe
```

## 文件清单

| 文件 | 说明 |
|------|------|
| `cimbar_tool/text_to_cimbar_png.py` | 文本目录批量转 cimbar PNG 的 Python 入口脚本 |
| `cimbar_tool/run_windows.bat` | Windows 11 虚拟环境安装与启动脚本 |
| `cimbar_tool/requirements.txt` | Python 依赖说明 |
| `cimbar_tool/README.md` | 安装与使用说明 |
| `docs/release_notes.md` | 本发布说明 |
