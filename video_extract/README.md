# Video Extract

面向 Windows 11 的视频 ROI 截图工具。

## 环境准备

建议使用 Python 3.10 或更新版本。

```bat
cd video_extract
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

也可以在 Windows 资源管理器中双击 `run_windows.bat` 安装依赖并启动。

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
