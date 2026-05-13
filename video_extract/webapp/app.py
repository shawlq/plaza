"""FastAPI backend for the video_extract web application.

Run from the ``video_extract`` directory with:
    python -m uvicorn webapp.app:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import atexit
import hashlib
import json
import mimetypes
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import quote

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


WEBAPP_ROOT = Path(__file__).resolve().parent
STATIC_ROOT = WEBAPP_ROOT / "static"
DATA_ROOT = Path(os.environ.get("VIDEO_EXTRACT_WEBAPP_DATA", WEBAPP_ROOT / "data")).resolve()
VIDEOS_ROOT = DATA_ROOT / "videos"
UPLOADS_ROOT = DATA_ROOT / "uploads"

VIDEO_EXTENSIONS = {
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".wmv",
    ".m4v",
    ".webm",
}
UPLOAD_METADATA_SUFFIX = ".json"
AUTOSAVE_SUFFIX = ".autosave.json"
CHUNK_SIZE = 1024 * 1024
UPLOAD_ID_PATTERN = re.compile(r"^[a-f0-9]{24}$")

app = FastAPI(title="Video Extract WebApp", version="0.4")
_annotation_sessions: dict[str, dict[str, Any]] = {}


class UploadInitRequest(BaseModel):
    filename: str = Field(min_length=1)
    size: int = Field(ge=0)
    mime_type: str | None = None
    last_modified: int | None = None


class Point(BaseModel):
    x: int
    y: int


class AnnotationRecordRequest(BaseModel):
    video_id: str = Field(min_length=1)
    frame_id: int = Field(ge=0)
    roi_points: list[Point] = Field(min_length=4, max_length=4)
    output_dir: str = Field(min_length=1)
    current_time: float | None = Field(default=None, ge=0)


class AnnotationSaveRequest(BaseModel):
    video_id: str = Field(min_length=1)


class AnnotationExportRequest(BaseModel):
    video_id: str = Field(min_length=1)


def _angle_sorted_points_for_warp(points: list[tuple[int, int]]) -> list[tuple[float, float]]:
    points_array = np.array(points, dtype=np.float32)
    center = points_array.mean(axis=0)
    angles = np.arctan2(points_array[:, 1] - center[1], points_array[:, 0] - center[0])
    sorted_points = points_array[np.argsort(angles)]
    return [(float(x), float(y)) for x, y in sorted_points]


def order_quad_points_for_warp(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Order four ROI points as top-left, top-right, bottom-right, bottom-left (desktop ``main.py``)."""

    if len(points) != 4:
        return []

    polygon = _angle_sorted_points_for_warp(points)
    if len(polygon) != 4:
        return []

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


def is_convex_quad_for_warp(points: list[tuple[int, int]]) -> bool:
    if len(points) != 4:
        return False
    contour = np.array(_angle_sorted_points_for_warp(points), dtype=np.float32)
    area = cv2.contourArea(contour)
    if area <= 1.0:
        return False
    return bool(cv2.isContourConvex(contour.astype(np.int32)))


def warp_roi_to_rectangle(
    frame_bgr: np.ndarray,
    points: list[tuple[int, int]],
) -> Optional[np.ndarray]:
    """Perspective-rectify ROI quad; geometry and interpolation match desktop ``main.py``."""

    ordered_points = order_quad_points_for_warp(points)
    if len(ordered_points) != 4 or not is_convex_quad_for_warp(ordered_points):
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
        flags=cv2.INTER_LINEAR,
    )


@app.on_event("startup")
def _ensure_data_directories() -> None:
    for directory in (VIDEOS_ROOT, UPLOADS_ROOT):
        directory.mkdir(parents=True, exist_ok=True)


@app.on_event("shutdown")
def _flush_sessions_on_shutdown() -> None:
    _flush_all_sessions()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace("\x00", "")
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    name = name.strip(" .")
    if not name:
        raise HTTPException(status_code=400, detail="文件名无效")
    suffix = Path(name).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的视频格式: {suffix or '(无后缀)'}")
    return name


def _upload_id_for(filename: str, size: int, last_modified: int | None) -> str:
    raw = f"{filename}:{size}:{last_modified or 0}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _upload_metadata_path(upload_id: str) -> Path:
    if not UPLOAD_ID_PATTERN.fullmatch(upload_id):
        raise HTTPException(status_code=404, detail="上传会话不存在")
    return UPLOADS_ROOT / f"{upload_id}{UPLOAD_METADATA_SUFFIX}"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="资源不存在") from None
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"JSON 文件损坏: {path.name}") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def _pick_final_video_path(safe_name: str, upload_id: str, size: int) -> Path:
    candidate = VIDEOS_ROOT / safe_name
    if not candidate.exists() or candidate.stat().st_size == size:
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    return VIDEOS_ROOT / f"{stem}_{upload_id[:8]}{suffix}"


def _video_path_from_id(video_id: str) -> Path:
    filename = Path(video_id).name
    if filename != video_id:
        raise HTTPException(status_code=400, detail="视频 ID 无效")
    path = (VIDEOS_ROOT / filename).resolve()
    if not path.is_file() or path.parent != VIDEOS_ROOT:
        raise HTTPException(status_code=404, detail="视频不存在")
    if path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=404, detail="视频不存在")
    return path


def _video_metadata(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    metadata: dict[str, Any] = {
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "frame_count": 0,
        "duration_seconds": 0.0,
    }
    try:
        if capture.isOpened():
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
            fps = float(capture.get(cv2.CAP_PROP_FPS)) or 0.0
            metadata.update(
                {
                    "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 0,
                    "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 0,
                    "fps": fps,
                    "frame_count": frame_count,
                    "duration_seconds": frame_count / fps if fps > 0 else 0.0,
                }
            )
    finally:
        capture.release()
    return metadata


def _video_payload(path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "id": path.name,
        "name": path.name,
        "path": str(path),
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "stream_url": f"/api/videos/{quote(path.name)}/stream",
        "default_output_dir": str(path.with_suffix("")),
        "json_path": str(path.with_suffix(".json")),
        "autosave_path": str(path.with_name(f"{path.stem}{AUTOSAVE_SUFFIX}")),
        "metadata": _video_metadata(path),
    }


def _part_path(upload_id: str) -> Path:
    return UPLOADS_ROOT / f"{upload_id}.part"


def _upload_status(metadata: dict[str, Any]) -> dict[str, Any]:
    upload_id = metadata["upload_id"]
    part_path = Path(metadata["part_path"])
    final_path = Path(metadata["final_path"])
    completed = bool(metadata.get("completed")) and final_path.exists()
    offset = final_path.stat().st_size if completed else (part_path.stat().st_size if part_path.exists() else 0)
    payload: dict[str, Any] = {
        "upload_id": upload_id,
        "filename": metadata["filename"],
        "size": metadata["size"],
        "offset": offset,
        "completed": completed,
    }
    if completed:
        payload["video"] = _video_payload(final_path)
    return payload


def _load_or_create_session(video_path: Path) -> dict[str, Any]:
    video_id = video_path.name
    if video_id in _annotation_sessions:
        return _annotation_sessions[video_id]

    autosave_path = video_path.with_name(f"{video_path.stem}{AUTOSAVE_SUFFIX}")
    json_path = video_path.with_suffix(".json")
    if autosave_path.exists():
        session = _read_json(autosave_path)
    elif json_path.exists():
        session = _read_json(json_path)
    else:
        session = {
            "video": _video_payload(video_path),
            "records": [],
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
    _annotation_sessions[video_id] = session
    return session


def _cross(o: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _is_convex_quad(points: list[tuple[int, int]]) -> bool:
    if len(points) != 4 or len(set(points)) != 4:
        return False
    signs: list[int] = []
    for index in range(4):
        value = _cross(points[index], points[(index + 1) % 4], points[(index + 2) % 4])
        if value == 0:
            return False
        signs.append(1 if value > 0 else -1)
    return all(sign == signs[0] for sign in signs)


def _validate_roi_points(video_path: Path, points: list[Point]) -> list[dict[str, int]]:
    metadata = _video_metadata(video_path)
    width = int(metadata.get("width") or 0)
    height = int(metadata.get("height") or 0)
    raw_points = [(point.x, point.y) for point in points]
    if width > 0 and height > 0:
        for x, y in raw_points:
            if x < 0 or y < 0 or x >= width or y >= height:
                raise HTTPException(status_code=400, detail="ROI 点超出视频范围")
    if not _is_convex_quad(raw_points):
        raise HTTPException(status_code=400, detail="ROI 必须是按顺序连接的凸四边形")
    return [{"x": x, "y": y} for x, y in raw_points]


def _flush_session(video_id: str, session: dict[str, Any], final: bool) -> Path:
    video_path = _video_path_from_id(video_id)
    path = video_path.with_suffix(".json") if final else video_path.with_name(f"{video_path.stem}{AUTOSAVE_SUFFIX}")
    session["updated_at"] = _utc_now()
    _write_json_atomic(path, session)
    return path


def _flush_all_sessions() -> None:
    for video_id, session in list(_annotation_sessions.items()):
        try:
            if session.get("records"):
                _flush_session(video_id, session, final=True)
        except Exception:
            # Best effort during interpreter shutdown.
            pass


atexit.register(_flush_all_sessions)


@app.post("/api/uploads/init")
def init_upload(payload: UploadInitRequest) -> dict[str, Any]:
    _ensure_data_directories()
    safe_name = _safe_filename(payload.filename)
    upload_id = _upload_id_for(safe_name, payload.size, payload.last_modified)
    metadata_path = _upload_metadata_path(upload_id)

    if metadata_path.exists():
        return _upload_status(_read_json(metadata_path))

    final_path = _pick_final_video_path(safe_name, upload_id, payload.size)
    if final_path.exists() and final_path.stat().st_size == payload.size:
        metadata = {
            "upload_id": upload_id,
            "filename": final_path.name,
            "size": payload.size,
            "part_path": str(_part_path(upload_id)),
            "final_path": str(final_path),
            "completed": True,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        }
        _write_json_atomic(metadata_path, metadata)
        return _upload_status(metadata)

    metadata = {
        "upload_id": upload_id,
        "filename": final_path.name,
        "original_filename": payload.filename,
        "size": payload.size,
        "mime_type": payload.mime_type,
        "part_path": str(_part_path(upload_id)),
        "final_path": str(final_path),
        "completed": False,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
    }
    _write_json_atomic(metadata_path, metadata)
    return _upload_status(metadata)


@app.get("/api/uploads/{upload_id}")
def get_upload_status(upload_id: str) -> dict[str, Any]:
    return _upload_status(_read_json(_upload_metadata_path(upload_id)))


@app.patch("/api/uploads/{upload_id}")
async def upload_chunk(upload_id: str, request: Request, offset: int) -> dict[str, Any]:
    if offset < 0:
        raise HTTPException(status_code=400, detail="offset 无效")
    metadata_path = _upload_metadata_path(upload_id)
    metadata = _read_json(metadata_path)
    if metadata.get("completed"):
        return _upload_status(metadata)

    size = int(metadata["size"])
    part_path = Path(metadata["part_path"])
    final_path = Path(metadata["final_path"])
    part_path.parent.mkdir(parents=True, exist_ok=True)
    current_offset = part_path.stat().st_size if part_path.exists() else 0
    if offset != current_offset:
        raise HTTPException(
            status_code=409,
            detail={"message": "上传偏移不匹配", "offset": current_offset},
        )

    written = 0
    with part_path.open("ab") as target:
        async for chunk in request.stream():
            if not chunk:
                continue
            written += len(chunk)
            if current_offset + written > size:
                raise HTTPException(status_code=413, detail="上传数据超过声明大小")
            target.write(chunk)

    new_offset = current_offset + written
    metadata["updated_at"] = _utc_now()
    if new_offset == size:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(part_path), str(final_path))
        metadata["completed"] = True
    _write_json_atomic(metadata_path, metadata)
    return _upload_status(metadata)


@app.get("/api/videos")
def list_videos() -> dict[str, Any]:
    _ensure_data_directories()
    videos = [
        _video_payload(path)
        for path in sorted(VIDEOS_ROOT.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return {"videos": videos}


@app.get("/api/videos/{video_id}")
def get_video(video_id: str) -> dict[str, Any]:
    return {"video": _video_payload(_video_path_from_id(video_id))}


def _file_iterator(path: Path, start: int, end: int) -> Iterable[bytes]:
    with path.open("rb") as file_obj:
        file_obj.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = file_obj.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def _parse_byte_range(range_header: str, file_size: int) -> tuple[int, int]:
    try:
        unit, value = range_header.split("=", 1)
        if unit.strip().lower() != "bytes":
            raise ValueError
        ranges = [item.strip() for item in value.split(",") if item.strip()]
        if len(ranges) != 1:
            raise ValueError
        start_text, end_text = ranges[0].split("-", 1)
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Range 请求无效") from exc

    if start_text:
        try:
            start = int(start_text)
            end = int(end_text) if end_text else file_size - 1
        except ValueError as exc:
            raise HTTPException(status_code=416, detail="Range 请求无效") from exc
    else:
        try:
            suffix_length = int(end_text)
        except ValueError as exc:
            raise HTTPException(status_code=416, detail="Range 请求无效") from exc
        if suffix_length <= 0:
            raise HTTPException(status_code=416, detail="Range 请求无效")
        start = max(file_size - suffix_length, 0)
        end = file_size - 1

    if start < 0 or end < start or start >= file_size:
        raise HTTPException(status_code=416, detail="Range 请求超出文件大小")
    return start, min(end, file_size - 1)


@app.get("/api/videos/{video_id}/stream")
def stream_video(video_id: str, request: Request):
    path = _video_path_from_id(video_id)
    file_size = path.stat().st_size
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    range_header = request.headers.get("range")
    if not range_header:
        response = FileResponse(path, media_type=media_type, filename=path.name)
        response.headers["Accept-Ranges"] = "bytes"
        return response

    start, end = _parse_byte_range(range_header, file_size)
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(end - start + 1),
    }
    return StreamingResponse(
        _file_iterator(path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


@app.get("/api/annotations/{video_id}")
def get_annotations(video_id: str) -> dict[str, Any]:
    video_path = _video_path_from_id(video_id)
    session = _load_or_create_session(video_path)
    return {
        "annotation": session,
        "record_count": len(session.get("records", [])),
        "json_path": str(video_path.with_suffix(".json")),
        "autosave_path": str(video_path.with_name(f"{video_path.stem}{AUTOSAVE_SUFFIX}")),
    }


@app.post("/api/annotations/record")
def record_annotation(payload: AnnotationRecordRequest) -> dict[str, Any]:
    video_path = _video_path_from_id(payload.video_id)
    output_dir = Path(payload.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    session = _load_or_create_session(video_path)
    roi_points = _validate_roi_points(video_path, payload.roi_points)
    record = {
        "frame_id": payload.frame_id,
        "roi_points": roi_points,
        "output_dir": str(output_dir),
        "current_time": payload.current_time,
        "recorded_at": _utc_now(),
    }
    session["video"] = _video_payload(video_path)
    session["output_dir"] = str(output_dir)
    session.setdefault("records", []).append(record)
    draft_path = _flush_session(payload.video_id, session, final=False)
    return {
        "record": record,
        "record_count": len(session["records"]),
        "autosave_path": str(draft_path),
    }


@app.post("/api/annotations/save")
def save_annotations(payload: AnnotationSaveRequest) -> dict[str, Any]:
    video_path = _video_path_from_id(payload.video_id)
    session = _load_or_create_session(video_path)
    final_path = _flush_session(payload.video_id, session, final=True)
    autosave_path = video_path.with_name(f"{video_path.stem}{AUTOSAVE_SUFFIX}")
    if autosave_path.exists():
        autosave_path.unlink()
    return {
        "saved": True,
        "record_count": len(session.get("records", [])),
        "json_path": str(final_path),
    }


@app.post("/api/annotations/export-images")
def export_annotation_images(payload: AnnotationExportRequest) -> dict[str, Any]:
    """Save final JSON, then render each record to PNG using the saved file as source of truth."""

    video_path = _video_path_from_id(payload.video_id)
    session = _load_or_create_session(video_path)
    final_path = _flush_session(payload.video_id, session, final=True)
    autosave_path = video_path.with_name(f"{video_path.stem}{AUTOSAVE_SUFFIX}")
    if autosave_path.exists():
        autosave_path.unlink()

    data = json.loads(final_path.read_text(encoding="utf-8"))
    records = data.get("records") or []
    if not records:
        raise HTTPException(status_code=400, detail="没有可导出的记录，请先「记录」。")

    stem = video_path.stem
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise HTTPException(status_code=500, detail="无法打开视频文件")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    exported: list[str] = []
    errors: list[dict[str, Any]] = []

    try:
        for index, rec in enumerate(records):
            try:
                frame_id = int(rec["frame_id"])
                roi_raw = rec.get("roi_points") or []
                if len(roi_raw) != 4:
                    raise ValueError("roi_points 必须为 4 个点")
                points = [(int(p["x"]), int(p["y"])) for p in roi_raw]
                output_dir_text = str(rec.get("output_dir") or "").strip()
                if not output_dir_text:
                    raise ValueError("output_dir 为空")
                out_dir = Path(output_dir_text).expanduser().resolve()
                out_dir.mkdir(parents=True, exist_ok=True)

                if total_frames and (frame_id < 0 or frame_id >= total_frames):
                    raise ValueError(f"frame_id 超出范围: {frame_id}")

                capture.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise ValueError(f"无法读取帧 {frame_id}")

                warped = warp_roi_to_rectangle(frame, points)
                if warped is None or warped.size == 0:
                    raise ValueError("ROI 透视矫正失败")

                out_path = out_dir / f"{stem}_{frame_id}.png"
                if not cv2.imwrite(
                    str(out_path),
                    warped,
                    [int(cv2.IMWRITE_PNG_COMPRESSION), 1],
                ):
                    raise ValueError(f"无法写入图像: {out_path}")
                exported.append(str(out_path))
            except Exception as exc:
                errors.append(
                    {
                        "index": index,
                        "frame_id": rec.get("frame_id"),
                        "error": str(exc),
                    }
                )
    finally:
        capture.release()

    return {
        "json_path": str(final_path),
        "exported_count": len(exported),
        "paths": exported,
        "errors": errors,
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.mount("/", StaticFiles(directory=STATIC_ROOT, html=True), name="static")
