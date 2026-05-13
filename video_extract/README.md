# Video Extract

面向 Windows 11 的视频 ROI 截图工具，并提供 Ubuntu 22.04 + NVIDIA GPU 环境可部署的 WebApp。

## 环境准备

建议使用 Python 3.10 或更新版本。

```bat
cd video_extract
python -m venv .venv
.venv\Scripts\activate
python -m pip install PySide6 opencv-python numpy fastapi "uvicorn[standard]"
python main.py
```

也可以在 Windows 资源管理器中双击 `run_windows.bat` 安装依赖并启动。依赖清单见 `docs/release_notes.md` 中的「Python 依赖」。

## WebApp

WebApp 位于 `webapp/`，后端使用 FastAPI，前端为静态 HTML/CSS/JavaScript，无需前端构建步骤。默认数据目录为 `video_extract/webapp/data/`，可通过环境变量 `VIDEO_EXTRACT_WEBAPP_DATA` 指定到更大的磁盘路径。

```bash
cd video_extract
python -m pip install PySide6 opencv-python numpy fastapi "uvicorn[standard]"
python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://服务器IP:8000/` 后可使用：

- 分片上传视频，上传中断后选择同一文件再次点击“上传/继续上传”即可从服务端偏移继续。
- 从“在线视频”下拉框选择已经上传的视频并在线播放。
- 快捷键：空格播放/暂停，左方向键上一帧，右方向键下一帧。
- 点击 `ROIpoly` 后在视频区域依次选择 4 个点，形成凸四边形 ROI。
- 保存目录默认是视频同目录下与视频同名、无后缀的文件夹，也可在页面输入服务端目录路径。
- 点击“记录”会记录当前 `frame_id`、ROI 4 个角点、保存目录等信息到服务端内存和 autosave 草稿；点击“保存”会写入视频同名的 `{视频名无后缀}.json`，服务端退出时也会尽力写入内存记录。

## 功能

- 打开常见视频文件并播放/暂停。
- 支持上一帧、下一帧、2×、4×播放速度。
- 快捷键：
  - 空格：播放/暂停
  - 左方向键：上一帧
  - 右方向键：下一帧
  - 回车：截屏
- 视频上方提供进度条，可用鼠标左键点击或拖拽定位。
- 进度条右侧显示当前视频时间和总时长。
- ROI 选择默认覆盖完整视频区域，也可点击“ROI选择”后在视频区拖拽矩形。
- ROI 信息显示 4 个角点的原始视频像素坐标。
- 点击“ROIpoly”后可在视频区选择 4 个点，形成凸四边形 ROI；工具会自动按左上、右上、右下、左下排序。
- 截屏会将四边形 ROI 透视矫正为正矩形图片，输出为 PNG。
- 保存目录默认是视频同级目录下与视频同名、无后缀的文件夹。
