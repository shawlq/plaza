"""Windows-friendly video ROI screenshot tool.

Run with:
    python winapp.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPolygonF,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


class SeekSlider(QSlider):
    """A horizontal slider that seeks immediately on left click and drag."""

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton:
            self._set_value_from_position(event.position().x())
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        if event.buttons() & Qt.LeftButton:
            self._set_value_from_position(event.position().x())
            event.accept()
        super().mouseMoveEvent(event)

    def _set_value_from_position(self, x_pos: float) -> None:
        if self.maximum() <= self.minimum() or self.width() <= 0:
            return
        usable_width = max(1, self.width())
        ratio = min(1.0, max(0.0, x_pos / usable_width))
        value = round(self.minimum() + ratio * (self.maximum() - self.minimum()))
        self.setValue(value)
        self.sliderMoved.emit(value)


class VideoCanvas(QWidget):
    """Video display widget with ROI drawing and selection support."""

    roi_points_selected = Signal(object)
    roi_selection_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumSize(QSize(800, 450))
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self._image: Optional[QImage] = None
        self._video_size = QSize(0, 0)
        self._display_rect = QRectF()
        self._roi_points: list[tuple[int, int]] = []
        self._selection_mode: Optional[str] = None
        self._dragging = False
        self._drag_start = QPointF()
        self._drag_end = QPointF()
        self._poly_points_display: list[QPointF] = []

    def set_frame(self, frame_bgr: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        bytes_per_line = channels * width
        self._image = QImage(
            rgb.data,
            width,
            height,
            bytes_per_line,
            QImage.Format_RGB888,
        ).copy()
        self._video_size = QSize(width, height)
        self._update_display_rect()
        self.update()

    def clear(self) -> None:
        self._image = None
        self._video_size = QSize(0, 0)
        self._roi_points = []
        self._display_rect = QRectF()
        self.update()

    def set_roi_points(self, points: list[tuple[int, int]]) -> None:
        self._roi_points = list(points)
        self.update()

    def set_roi_selection_mode(self, mode: Optional[str]) -> None:
        self._selection_mode = mode
        self._dragging = False
        self._poly_points_display = []
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt override
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.black)

        if self._image is None or self._display_rect.isEmpty():
            painter.setPen(QPen(Qt.lightGray))
            painter.drawText(self.rect(), Qt.AlignCenter, "请打开视频")
            return

        painter.drawImage(self._display_rect, self._image)

        if len(self._roi_points) == 4:
            painter.setPen(QPen(Qt.green, 2))
            display_points = [self._original_to_display_point(point) for point in self._roi_points]
            painter.drawPolygon(QPolygonF(display_points))
            for index, point in enumerate(display_points, start=1):
                painter.drawEllipse(point, 4, 4)
                painter.drawText(point + QPointF(6, -6), f"P{index}")

        if self._dragging:
            painter.setPen(QPen(Qt.yellow, 2, Qt.DashLine))
            painter.drawRect(QRectF(self._drag_start, self._drag_end).normalized())

        if self._selection_mode == "poly" and self._poly_points_display:
            painter.setPen(QPen(Qt.yellow, 2, Qt.DashLine))
            for index, point in enumerate(self._poly_points_display, start=1):
                painter.drawEllipse(point, 5, 5)
                painter.drawText(point + QPointF(6, -6), f"P{index}")
                if index > 1:
                    painter.drawLine(self._poly_points_display[index - 2], point)

    def resizeEvent(self, event):  # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._update_display_rect()

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if (
            self._selection_mode == "rect"
            and event.button() == Qt.LeftButton
            and self._display_rect.contains(event.position())
        ):
            self._dragging = True
            self._drag_start = self._clamp_to_display(event.position())
            self._drag_end = self._drag_start
            self.update()
            event.accept()
            return
        if (
            self._selection_mode == "poly"
            and event.button() == Qt.LeftButton
            and self._display_rect.contains(event.position())
        ):
            self._poly_points_display.append(self._clamp_to_display(event.position()))
            if len(self._poly_points_display) == 4:
                points = [
                    self._display_to_original_point(point)
                    for point in self._poly_points_display
                ]
                self.roi_points_selected.emit(points)
                self.roi_selection_finished.emit()
                self._poly_points_display = []
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt override
        if self._dragging:
            self._drag_end = self._clamp_to_display(event.position())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        if self._dragging and event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_end = self._clamp_to_display(event.position())
            roi = self._display_to_original_rect(
                QRectF(self._drag_start, self._drag_end).normalized()
            )
            if roi.width() > 0 and roi.height() > 0:
                self.roi_points_selected.emit(rect_to_points(roi))
            self.roi_selection_finished.emit()
            self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _update_display_rect(self) -> None:
        if self._video_size.isEmpty() or self.width() <= 0 or self.height() <= 0:
            self._display_rect = QRectF()
            return

        video_ratio = self._video_size.width() / self._video_size.height()
        widget_ratio = self.width() / max(1, self.height())
        if widget_ratio > video_ratio:
            display_height = self.height()
            display_width = display_height * video_ratio
        else:
            display_width = self.width()
            display_height = display_width / video_ratio

        left = (self.width() - display_width) / 2.0
        top = (self.height() - display_height) / 2.0
        self._display_rect = QRectF(left, top, display_width, display_height)

    def _clamp_to_display(self, point: QPointF) -> QPointF:
        return QPointF(
            min(max(point.x(), self._display_rect.left()), self._display_rect.right()),
            min(max(point.y(), self._display_rect.top()), self._display_rect.bottom()),
        )

    def _display_to_original_rect(self, display_rect: QRectF) -> QRect:
        if self._video_size.isEmpty() or self._display_rect.isEmpty():
            return QRect()

        left_ratio = (display_rect.left() - self._display_rect.left()) / self._display_rect.width()
        top_ratio = (display_rect.top() - self._display_rect.top()) / self._display_rect.height()
        right_ratio = (display_rect.right() - self._display_rect.left()) / self._display_rect.width()
        bottom_ratio = (display_rect.bottom() - self._display_rect.top()) / self._display_rect.height()

        x1 = int(np.floor(left_ratio * self._video_size.width()))
        y1 = int(np.floor(top_ratio * self._video_size.height()))
        x2 = int(np.ceil(right_ratio * self._video_size.width()))
        y2 = int(np.ceil(bottom_ratio * self._video_size.height()))

        x1 = min(max(0, x1), self._video_size.width() - 1)
        y1 = min(max(0, y1), self._video_size.height() - 1)
        x2 = min(max(x1 + 1, x2), self._video_size.width())
        y2 = min(max(y1 + 1, y2), self._video_size.height())
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _display_to_original_point(self, point: QPointF) -> tuple[int, int]:
        if self._video_size.isEmpty() or self._display_rect.isEmpty():
            return (0, 0)

        x_ratio = (point.x() - self._display_rect.left()) / self._display_rect.width()
        y_ratio = (point.y() - self._display_rect.top()) / self._display_rect.height()
        x = int(round(x_ratio * (self._video_size.width() - 1)))
        y = int(round(y_ratio * (self._video_size.height() - 1)))
        return (
            min(max(0, x), self._video_size.width() - 1),
            min(max(0, y), self._video_size.height() - 1),
        )

    def _original_to_display_point(self, point: tuple[int, int]) -> QPointF:
        if self._video_size.isEmpty() or self._display_rect.isEmpty():
            return QPointF()

        x_scale = self._display_rect.width() / max(1, self._video_size.width() - 1)
        y_scale = self._display_rect.height() / max(1, self._video_size.height() - 1)
        return QPointF(
            self._display_rect.left() + point[0] * x_scale,
            self._display_rect.top() + point[1] * y_scale,
        )


class VideoExtractWindow(QMainWindow):
    """Main window for loading video, selecting ROI, and saving screenshots."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Extract - ROI 截图工具")
        self.resize(1200, 800)
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available_h = screen.availableGeometry().height()
            if self.height() > available_h:
                new_h = int(self.height() * 0.8)
                self.resize(self.width(), min(new_h, max(1, available_h - 20)))

        self.capture: Optional[cv2.VideoCapture] = None
        self.video_path: Optional[Path] = None
        self.current_frame: Optional[np.ndarray] = None
        self.current_frame_index = 0
        self.total_frames = 0
        self.fps = 25.0
        self.duration_seconds = 0.0
        self.playback_speed = 1.0
        self.is_playing = False
        self.roi_points: list[tuple[int, int]] = []
        self._updating_slider = False

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._play_next_frame)

        self.canvas = VideoCanvas()
        self.progress_slider = SeekSlider(Qt.Horizontal)
        self.progress_slider.setEnabled(False)
        self.progress_slider.sliderPressed.connect(self._pause_for_seek)
        self.progress_slider.sliderMoved.connect(self._seek_to_frame)
        self.progress_slider.sliderReleased.connect(self._seek_to_slider_value)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.time_label.setMinimumWidth(210)

        self.open_button = QPushButton("打开视频")
        self.play_button = QPushButton("播放")
        self.prev_button = QPushButton("上一帧")
        self.next_button = QPushButton("下一帧")
        self.speed_2x_button = QPushButton("2×")
        self.speed_4x_button = QPushButton("4×")
        self.roi_poly_button = QPushButton("ROIpoly")
        self.capture_button = QPushButton("截屏")
        self.roi_info_label = QLabel("ROI: 未加载视频")
        self.roi_info_label.setWordWrap(True)
        self.output_dir_edit = QLineEdit()
        self.output_dir_button = QPushButton("选择目录")

        self._build_ui()
        self._wire_events()
        self._update_controls_enabled(False)
        self.setStatusBar(QStatusBar(self))

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self._release_capture()
        super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)

        progress_layout = QHBoxLayout()
        progress_layout.addWidget(self.progress_slider, stretch=1)
        progress_layout.addWidget(self.time_label)
        root_layout.addLayout(progress_layout)
        root_layout.addWidget(self.canvas, stretch=1)

        control_layout = QHBoxLayout()
        for button in (
            self.open_button,
            self.play_button,
            self.prev_button,
            self.next_button,
            self.speed_2x_button,
            self.speed_4x_button,
            self.roi_poly_button,
            self.capture_button,
        ):
            control_layout.addWidget(button)
        control_layout.addWidget(self.roi_info_label, stretch=1)
        root_layout.addLayout(control_layout)

        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("保存目录:"))
        output_layout.addWidget(self.output_dir_edit, stretch=1)
        output_layout.addWidget(self.output_dir_button)
        root_layout.addLayout(output_layout)

        self.setCentralWidget(central)

        self.speed_2x_button.setCheckable(True)
        self.speed_4x_button.setCheckable(True)
        speed_group = QButtonGroup(self)
        speed_group.setExclusive(True)
        speed_group.addButton(self.speed_2x_button)
        speed_group.addButton(self.speed_4x_button)

        self.roi_poly_button.setCheckable(True)

        toolbar = QToolBar("快捷键")
        toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, toolbar)
        shortcut_hint = QAction(
            "快捷键: Space 播放/暂停 | ← 上一帧 | → 下一帧 | Enter 截屏",
            self,
        )
        shortcut_hint.setEnabled(False)
        toolbar.addAction(shortcut_hint)

    def _wire_events(self) -> None:
        self.open_button.clicked.connect(self.open_video)
        self.play_button.clicked.connect(self.toggle_play_pause)
        self.prev_button.clicked.connect(self.previous_frame)
        self.next_button.clicked.connect(self.next_frame)
        self.speed_2x_button.clicked.connect(lambda: self._set_speed(2.0))
        self.speed_4x_button.clicked.connect(lambda: self._set_speed(4.0))
        self.roi_poly_button.toggled.connect(self._set_poly_roi_selection)
        self.capture_button.clicked.connect(self.save_screenshot)
        self.output_dir_button.clicked.connect(self.choose_output_dir)
        self.canvas.roi_points_selected.connect(self._on_roi_points_selected)
        self.canvas.roi_selection_finished.connect(self._finish_roi_selection)

        QShortcut(QKeySequence("Space"), self, activated=self.toggle_play_pause)
        QShortcut(QKeySequence("Left"), self, activated=self.previous_frame)
        QShortcut(QKeySequence("Right"), self, activated=self.next_frame)
        QShortcut(QKeySequence("Return"), self, activated=self.save_screenshot)
        QShortcut(QKeySequence("Enter"), self, activated=self.save_screenshot)

    def open_video(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "打开视频",
            str(Path.home()),
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.m4v);;All Files (*.*)",
        )
        if not file_path:
            return
        self.load_video(Path(file_path))

    def load_video(self, path: Path) -> None:
        self._release_capture()
        capture = cv2.VideoCapture(str(path))
        if not capture.isOpened():
            QMessageBox.critical(self, "打开失败", f"无法打开视频:\n{path}")
            self._update_controls_enabled(False)
            return

        self.capture = capture
        self.video_path = path
        self.total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        self.fps = float(capture.get(cv2.CAP_PROP_FPS)) or 25.0
        if self.fps <= 0:
            self.fps = 25.0
        self.duration_seconds = self.total_frames / self.fps if self.total_frames else 0.0

        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(max(0, self.total_frames - 1))
        self.progress_slider.setValue(0)

        default_dir = path.with_suffix("")
        self.output_dir_edit.setText(str(default_dir))
        try:
            default_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "目录创建失败",
                f"无法创建默认保存目录:\n{default_dir}\n\n{exc}",
            )

        if not self._read_frame(0):
            QMessageBox.critical(self, "读取失败", f"无法读取视频第一帧:\n{path}")
            self._release_capture()
            self._update_controls_enabled(False)
            return

        frame_height, frame_width = self.current_frame.shape[:2]
        self.roi_points = full_frame_points(frame_width, frame_height)
        self.canvas.set_roi_points(self.roi_points)
        self._update_roi_label()
        self._update_controls_enabled(True)
        self._update_time_label()
        self.statusBar().showMessage(f"已打开视频: {path}", 5000)

    def toggle_play_pause(self) -> None:
        if self.capture is None:
            return
        if self.is_playing:
            self._pause()
        else:
            if self.current_frame_index >= max(0, self.total_frames - 1):
                self._read_frame(0)
            self.is_playing = True
            self.play_button.setText("暂停")
            self._restart_timer()

    def previous_frame(self) -> None:
        if self.capture is None:
            return
        self._pause()
        self._read_frame(max(0, self.current_frame_index - 1))

    def next_frame(self) -> None:
        if self.capture is None:
            return
        self._pause()
        self._read_frame(min(max(0, self.total_frames - 1), self.current_frame_index + 1))

    def choose_output_dir(self) -> None:
        start_dir = self.output_dir_edit.text().strip()
        if not start_dir and self.video_path is not None:
            start_dir = str(self.video_path.parent)
        directory = QFileDialog.getExistingDirectory(self, "选择保存目录", start_dir)
        if directory:
            self.output_dir_edit.setText(directory)

    def save_screenshot(self) -> None:
        if self.capture is None or self.current_frame is None:
            return
        output_dir_text = self.output_dir_edit.text().strip()
        if not output_dir_text:
            QMessageBox.warning(self, "保存失败", "请先选择保存目录。")
            return

        output_dir = Path(output_dir_text)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", f"无法创建保存目录:\n{output_dir}\n\n{exc}")
            return

        if not self._read_frame(self.current_frame_index):
            QMessageBox.warning(self, "保存失败", "无法从视频重新读取当前帧。")
            return

        frame_height, frame_width = self.current_frame.shape[:2]
        roi_points = self._clamped_roi_points(frame_width, frame_height)
        crop = warp_roi_to_rectangle(
            self.current_frame,
            roi_points,
            interpolation=cv2.INTER_LANCZOS4,
        )
        if crop is None or crop.size == 0:
            QMessageBox.warning(self, "保存失败", "ROI 区域为空，无法截屏。")
            return

        stem = self.video_path.stem if self.video_path else "video"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = f"{stem}_frame_{self.current_frame_index:06d}_{timestamp}.png"
        output_path = output_dir / filename

        success = cv2.imwrite(str(output_path), crop)
        if not success:
            QMessageBox.critical(self, "保存失败", f"无法写入图像:\n{output_path}")
            return
        self.statusBar().showMessage(f"已保存截屏: {output_path}", 8000)

    def _read_frame(self, frame_index: int) -> bool:
        if self.capture is None:
            return False
        target = min(max(0, frame_index), max(0, self.total_frames - 1))
        self.capture.set(cv2.CAP_PROP_POS_FRAMES, target)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            return False

        self.current_frame = frame
        self.current_frame_index = target
        self.canvas.set_frame(frame)
        if len(self.roi_points) == 4:
            self.canvas.set_roi_points(self.roi_points)
        self._sync_slider_to_frame()
        self._update_time_label()
        return True

    def _play_next_frame(self) -> None:
        if self.capture is None:
            self._pause()
            return
        next_index = self.current_frame_index + 1
        if next_index >= self.total_frames:
            self._pause()
            return
        if not self._read_frame(next_index):
            self._pause()

    def _pause(self) -> None:
        self.play_timer.stop()
        self.is_playing = False
        self.play_button.setText("播放")

    def _pause_for_seek(self) -> None:
        self._pause()

    def _seek_to_slider_value(self) -> None:
        self._seek_to_frame(self.progress_slider.value())

    def _seek_to_frame(self, frame_index: int) -> None:
        if self._updating_slider or self.capture is None:
            return
        self._pause()
        self._read_frame(frame_index)

    def _set_speed(self, speed: float) -> None:
        self.playback_speed = speed
        if self.is_playing:
            self._restart_timer()
        self.statusBar().showMessage(f"播放速度: {speed:g}×", 3000)

    def _restart_timer(self) -> None:
        interval_ms = max(1, int(1000 / max(1.0, self.fps * self.playback_speed)))
        self.play_timer.start(interval_ms)

    def _set_poly_roi_selection(self, enabled: bool) -> None:
        if enabled:
            self._pause()
            self.statusBar().showMessage("请在视频区域依次点击 4 个 ROIpoly 角点。", 5000)
        self.canvas.set_roi_selection_mode("poly" if enabled and self.capture is not None else None)
        if enabled and self.capture is None:
            self.roi_poly_button.setChecked(False)

    def _finish_roi_selection(self) -> None:
        self.roi_poly_button.setChecked(False)
        self.canvas.set_roi_selection_mode(None)

    def _on_roi_points_selected(self, points: list[tuple[int, int]]) -> None:
        ordered_points = order_quad_points(points)
        if len(ordered_points) != 4 or not is_convex_quad(ordered_points):
            QMessageBox.warning(self, "ROI 无效", "请选择 4 个能依次连接成凸四边形的点。")
            return
        self.roi_points = ordered_points
        self.canvas.set_roi_points(self.roi_points)
        self._update_roi_label()

    def _clamped_roi_points(self, frame_width: int, frame_height: int) -> list[tuple[int, int]]:
        if len(self.roi_points) != 4:
            return full_frame_points(frame_width, frame_height)

        return [
            (
                min(max(0, x), frame_width - 1),
                min(max(0, y), frame_height - 1),
            )
            for x, y in self.roi_points
        ]

    def _update_roi_label(self) -> None:
        if len(self.roi_points) != 4:
            self.roi_info_label.setText("ROI: 未设置")
            return
        labels = ("左上", "右上", "右下", "左下")
        points_text = " ".join(
            f"P{index}{labels[index - 1]}=({x}, {y})"
            for index, (x, y) in enumerate(self.roi_points, start=1)
        )
        self.roi_info_label.setText(
            f"ROI: {points_text}"
        )

    def _sync_slider_to_frame(self) -> None:
        self._updating_slider = True
        self.progress_slider.setValue(self.current_frame_index)
        self._updating_slider = False

    def _update_time_label(self) -> None:
        current_seconds = self.current_frame_index / self.fps if self.fps else 0.0
        self.time_label.setText(
            f"{format_seconds(current_seconds)} / {format_seconds(self.duration_seconds)}"
        )

    def _update_controls_enabled(self, enabled: bool) -> None:
        for widget in (
            self.play_button,
            self.prev_button,
            self.next_button,
            self.speed_2x_button,
            self.speed_4x_button,
            self.roi_poly_button,
            self.capture_button,
            self.progress_slider,
            self.output_dir_button,
            self.output_dir_edit,
        ):
            widget.setEnabled(enabled)

    def _release_capture(self) -> None:
        self._pause()
        if self.capture is not None:
            self.capture.release()
        self.capture = None


def rect_to_points(rect: QRect) -> list[tuple[int, int]]:
    """Convert a QRect ROI to ordered corner points in original pixel space."""

    right = rect.x() + rect.width() - 1
    bottom = rect.y() + rect.height() - 1
    return [
        (rect.x(), rect.y()),
        (right, rect.y()),
        (right, bottom),
        (rect.x(), bottom),
    ]


def full_frame_points(frame_width: int, frame_height: int) -> list[tuple[int, int]]:
    return rect_to_points(QRect(0, 0, frame_width, frame_height))


def order_quad_points(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Order four ROI points as top-left, top-right, bottom-right, bottom-left."""

    if len(points) != 4:
        return []

    polygon = _angle_sorted_points(points)
    if len(polygon) != 4:
        return []

    # The top edge is identified from pixel positions, not from click order.
    top_edge_index = min(
        range(4),
        key=lambda index: (
            (polygon[index][1] + polygon[(index + 1) % 4][1]) / 2,
            (polygon[index][0] + polygon[(index + 1) % 4][0]) / 2,
        ),
    )
    next_index = (top_edge_index + 1) % 4
    first = polygon[top_edge_index]
    second = polygon[next_index]

    if first[0] <= second[0]:
        ordered = [polygon[(top_edge_index + offset) % 4] for offset in range(4)]
    else:
        ordered = [polygon[(next_index - offset) % 4] for offset in range(4)]
    return [(int(round(x)), int(round(y))) for x, y in ordered]


def _angle_sorted_points(points: list[tuple[int, int]]) -> list[tuple[float, float]]:
    points_array = np.array(points, dtype=np.float32)
    center = points_array.mean(axis=0)
    angles = np.arctan2(points_array[:, 1] - center[1], points_array[:, 0] - center[0])
    sorted_points = points_array[np.argsort(angles)]
    return [(float(x), float(y)) for x, y in sorted_points]


def is_convex_quad(points: list[tuple[int, int]]) -> bool:
    if len(points) != 4:
        return False
    contour = np.array(_angle_sorted_points(points), dtype=np.float32)
    area = cv2.contourArea(contour)
    if area <= 1.0:
        return False
    return bool(cv2.isContourConvex(contour.astype(np.int32)))


def warp_roi_to_rectangle(
    frame_bgr: np.ndarray,
    points: list[tuple[int, int]],
    interpolation: int = cv2.INTER_LINEAR,
) -> Optional[np.ndarray]:
    ordered_points = order_quad_points(points)
    if len(ordered_points) != 4 or not is_convex_quad(ordered_points):
        return None

    src = np.array(ordered_points, dtype=np.float32)
    width_top = np.linalg.norm(src[1] - src[0])
    width_bottom = np.linalg.norm(src[2] - src[3])
    height_right = np.linalg.norm(src[2] - src[1])
    height_left = np.linalg.norm(src[3] - src[0])

    output_width = max(1, int(round(max(width_top, width_bottom))) + 1)
    output_height = max(1, int(round(max(height_right, height_left))) + 1)
    dst = np.array(
        [
            [0, 0],
            [output_width - 1, 0],
            [output_width - 1, output_height - 1],
            [0, output_height - 1],
        ],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(
        frame_bgr,
        matrix,
        (output_width, output_height),
        flags=interpolation,
    )


def format_seconds(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_seconds = total_ms // 1000
    sec = total_seconds % 60
    minutes_total = total_seconds // 60
    minute = minutes_total % 60
    hour = minutes_total // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d}.{ms:03d}"


def main() -> int:
    app = QApplication(sys.argv)
    window = VideoExtractWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
