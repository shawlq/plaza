const CHUNK_BYTES = 8 * 1024 * 1024;

const state = {
  videos: [],
  currentVideo: null,
  roiPoints: [],
  pendingRoiPoints: [],
  roiMode: false,
  annotation: { records: [] },
  unsaved: false,
};

const elements = {
  fileInput: document.querySelector("#fileInput"),
  uploadButton: document.querySelector("#uploadButton"),
  uploadProgressBar: document.querySelector("#uploadProgressBar"),
  uploadStatus: document.querySelector("#uploadStatus"),
  videoSelect: document.querySelector("#videoSelect"),
  refreshButton: document.querySelector("#refreshButton"),
  loadButton: document.querySelector("#loadButton"),
  videoInfo: document.querySelector("#videoInfo"),
  videoStage: document.querySelector("#videoStage"),
  videoPlayer: document.querySelector("#videoPlayer"),
  roiCanvas: document.querySelector("#roiCanvas"),
  emptyState: document.querySelector("#emptyState"),
  seekSlider: document.querySelector("#seekSlider"),
  timeLabel: document.querySelector("#timeLabel"),
  playButton: document.querySelector("#playButton"),
  prevButton: document.querySelector("#prevButton"),
  nextButton: document.querySelector("#nextButton"),
  roiPolyButton: document.querySelector("#roiPolyButton"),
  recordButton: document.querySelector("#recordButton"),
  saveButton: document.querySelector("#saveButton"),
  exportImagesButton: document.querySelector("#exportImagesButton"),
  outputDir: document.querySelector("#outputDir"),
  defaultDirButton: document.querySelector("#defaultDirButton"),
  roiInfo: document.querySelector("#roiInfo"),
  recordStatus: document.querySelector("#recordStatus"),
  recordsPreview: document.querySelector("#recordsPreview"),
};

async function apiJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) {
    return "-";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let size = value;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit === 0 ? 0 : 2)} ${units[unit]}`;
}

function formatSeconds(seconds) {
  const totalMs = Math.max(0, Math.round((seconds || 0) * 1000));
  const ms = totalMs % 1000;
  const totalSeconds = Math.floor(totalMs / 1000);
  const sec = totalSeconds % 60;
  const totalMinutes = Math.floor(totalSeconds / 60);
  const min = totalMinutes % 60;
  const hour = Math.floor(totalMinutes / 60);
  return `${String(hour).padStart(2, "0")}:${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}.${String(ms).padStart(3, "0")}`;
}

function getFps() {
  return state.currentVideo?.metadata?.fps > 0 ? state.currentVideo.metadata.fps : 25;
}

function getFrameCount() {
  return state.currentVideo?.metadata?.frame_count || Math.max(0, Math.round(elements.videoPlayer.duration * getFps()));
}

function currentFrameId() {
  const maxFrame = Math.max(0, getFrameCount() - 1);
  return Math.min(maxFrame, Math.max(0, Math.round(elements.videoPlayer.currentTime * getFps())));
}

function setStatus(element, message, isError = false) {
  element.textContent = message;
  element.classList.toggle("error", isError);
}

function setUploadProgress(offset, size) {
  const percent = size > 0 ? Math.min(100, (offset / size) * 100) : 0;
  elements.uploadProgressBar.style.width = `${percent}%`;
}

async function refreshVideos(preferredId = null) {
  const payload = await apiJson("/api/videos");
  state.videos = payload.videos || [];
  elements.videoSelect.innerHTML = "";
  if (state.videos.length === 0) {
    const option = document.createElement("option");
    option.textContent = "暂无在线视频";
    option.value = "";
    elements.videoSelect.append(option);
    elements.videoSelect.disabled = true;
    elements.loadButton.disabled = true;
    setStatus(elements.videoInfo, "尚未上传视频。");
    return;
  }

  for (const video of state.videos) {
    const option = document.createElement("option");
    option.value = video.id;
    option.textContent = `${video.name} (${formatBytes(video.size)})`;
    elements.videoSelect.append(option);
  }
  elements.videoSelect.disabled = false;
  elements.loadButton.disabled = false;
  if (preferredId) {
    elements.videoSelect.value = preferredId;
  }
  setStatus(elements.videoInfo, `共 ${state.videos.length} 个在线视频。`);
}

async function uploadSelectedFile() {
  const file = elements.fileInput.files?.[0];
  if (!file) {
    setStatus(elements.uploadStatus, "请先选择本地视频文件。", true);
    return;
  }

  elements.uploadButton.disabled = true;
  setUploadProgress(0, file.size);
  try {
    const initPayload = await apiJson("/api/uploads/init", {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        size: file.size,
        mime_type: file.type || null,
        last_modified: file.lastModified || null,
      }),
    });

    let offset = initPayload.offset || 0;
    if (initPayload.completed) {
      setUploadProgress(file.size, file.size);
      setStatus(elements.uploadStatus, `视频已存在: ${initPayload.video.name}`);
      await refreshVideos(initPayload.video.id);
      return;
    }

    const uploadId = initPayload.upload_id;
    setStatus(elements.uploadStatus, `开始上传，当前偏移 ${formatBytes(offset)} / ${formatBytes(file.size)}。`);
    while (offset < file.size) {
      const chunk = file.slice(offset, Math.min(offset + CHUNK_BYTES, file.size));
      const response = await fetch(`/api/uploads/${uploadId}?offset=${offset}`, {
        method: "PATCH",
        body: chunk,
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 409 && result.detail?.offset !== undefined) {
        offset = result.detail.offset;
        continue;
      }
      if (!response.ok) {
        throw new Error(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail || response.statusText));
      }
      offset = result.offset || offset + chunk.size;
      setUploadProgress(offset, file.size);
      setStatus(elements.uploadStatus, `上传中 ${formatBytes(offset)} / ${formatBytes(file.size)}。`);
      if (result.completed) {
        setStatus(elements.uploadStatus, `上传完成: ${result.video.name}`);
        await refreshVideos(result.video.id);
        await loadVideo(result.video.id);
        break;
      }
    }
  } catch (error) {
    setStatus(elements.uploadStatus, `上传中断，可再次点击继续上传: ${error.message}`, true);
  } finally {
    elements.uploadButton.disabled = false;
  }
}

async function prefetchAnnotationsForSelectedVideo() {
  const videoId = elements.videoSelect.value;
  if (!videoId || (state.currentVideo && state.currentVideo.id === videoId)) {
    return;
  }
  try {
    const annotations = await apiJson(`/api/annotations/${encodeURIComponent(videoId)}`);
    if (elements.videoSelect.value !== videoId || (state.currentVideo && state.currentVideo.id === videoId)) {
      return;
    }
    elements.recordsPreview.textContent = JSON.stringify(annotations.annotation?.records || [], null, 2);
    setStatus(
      elements.recordStatus,
      `已加载「${videoId}」的 JSON（${annotations.record_count || 0} 条）。点击「加载视频」以打开播放器并同步画布。`,
    );
  } catch (error) {
    setStatus(elements.recordStatus, `读取标注 JSON 失败: ${error.message}`, true);
  }
}

async function loadSelectedVideo() {
  const videoId = elements.videoSelect.value;
  if (videoId) {
    await loadVideo(videoId);
  }
}

async function loadVideo(videoId) {
  const [payload, annotations] = await Promise.all([
    apiJson(`/api/videos/${encodeURIComponent(videoId)}`),
    apiJson(`/api/annotations/${encodeURIComponent(videoId)}`),
  ]);

  state.currentVideo = payload.video;
  state.roiMode = false;
  state.pendingRoiPoints = [];
  state.roiPoints = fullFrameRoiPoints();
  state.annotation = annotations.annotation || { records: [] };
  state.unsaved = false;

  elements.videoPlayer.src = state.currentVideo.stream_url;
  elements.videoPlayer.load();
  elements.emptyState.style.display = "none";
  elements.outputDir.value = state.currentVideo.default_output_dir;
  elements.outputDir.disabled = false;
  elements.defaultDirButton.disabled = false;
  setControlsEnabled(true);
  updateVideoInfo();
  updateRoiInfo();
  drawRoiOverlay();

  if (state.annotation.output_dir) {
    elements.outputDir.value = state.annotation.output_dir;
  }
  elements.saveButton.disabled = false;
  elements.exportImagesButton.disabled = false;
  updateRecordsPreview();
  setStatus(
    elements.recordStatus,
    `已加载记录 ${annotations.record_count || 0} 条。JSON: ${annotations.json_path}`,
  );
}

function updateVideoInfo() {
  if (!state.currentVideo) {
    setStatus(elements.videoInfo, "暂无视频。");
    return;
  }
  const meta = state.currentVideo.metadata || {};
  const parts = [
    state.currentVideo.name,
    `${formatBytes(state.currentVideo.size)}`,
    `${meta.width || 0}x${meta.height || 0}`,
    `${(meta.fps || 0).toFixed(3)} fps`,
    `${meta.frame_count || 0} frames`,
  ];
  setStatus(elements.videoInfo, parts.join(" · "));
}

function setControlsEnabled(enabled) {
  for (const element of [
    elements.playButton,
    elements.prevButton,
    elements.nextButton,
    elements.roiPolyButton,
    elements.recordButton,
    elements.seekSlider,
  ]) {
    element.disabled = !enabled;
  }
}

function fullFrameRoiPoints() {
  const width = state.currentVideo?.metadata?.width || elements.videoPlayer.videoWidth || 0;
  const height = state.currentVideo?.metadata?.height || elements.videoPlayer.videoHeight || 0;
  if (width <= 0 || height <= 0) {
    return [];
  }
  return [
    { x: 0, y: 0 },
    { x: width - 1, y: 0 },
    { x: width - 1, y: height - 1 },
    { x: 0, y: height - 1 },
  ];
}

function togglePlayPause() {
  if (!state.currentVideo) {
    return;
  }
  if (elements.videoPlayer.paused) {
    elements.videoPlayer.play();
  } else {
    elements.videoPlayer.pause();
  }
}

function stepFrame(delta) {
  if (!state.currentVideo) {
    return;
  }
  elements.videoPlayer.pause();
  const fps = getFps();
  const frame = Math.min(Math.max(0, currentFrameId() + delta), Math.max(0, getFrameCount() - 1));
  elements.videoPlayer.currentTime = frame / fps;
  updateTimeline();
}

function updateTimeline() {
  if (!state.currentVideo) {
    elements.timeLabel.textContent = "00:00:00.000 / 00:00:00.000";
    return;
  }
  const frame = currentFrameId();
  const maxFrame = Math.max(0, getFrameCount() - 1);
  elements.seekSlider.max = String(maxFrame);
  elements.seekSlider.value = String(frame);
  elements.timeLabel.textContent = `${formatSeconds(elements.videoPlayer.currentTime)} / ${formatSeconds(elements.videoPlayer.duration || state.currentVideo.metadata?.duration_seconds || 0)}`;
}

function seekToSlider() {
  if (!state.currentVideo) {
    return;
  }
  elements.videoPlayer.pause();
  elements.videoPlayer.currentTime = Number(elements.seekSlider.value) / getFps();
  updateTimeline();
}

function getContentRect() {
  const width = elements.roiCanvas.width;
  const height = elements.roiCanvas.height;
  const videoWidth = state.currentVideo?.metadata?.width || elements.videoPlayer.videoWidth;
  const videoHeight = state.currentVideo?.metadata?.height || elements.videoPlayer.videoHeight;
  if (!videoWidth || !videoHeight || !width || !height) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
  const videoRatio = videoWidth / videoHeight;
  const canvasRatio = width / height;
  if (canvasRatio > videoRatio) {
    const displayHeight = height;
    const displayWidth = displayHeight * videoRatio;
    return { left: (width - displayWidth) / 2, top: 0, width: displayWidth, height: displayHeight };
  }
  const displayWidth = width;
  const displayHeight = displayWidth / videoRatio;
  return { left: 0, top: (height - displayHeight) / 2, width: displayWidth, height: displayHeight };
}

function resizeCanvas() {
  const rect = elements.videoStage.getBoundingClientRect();
  elements.roiCanvas.width = Math.max(1, Math.round(rect.width));
  elements.roiCanvas.height = Math.max(1, Math.round(rect.height));
  drawRoiOverlay();
}

function pointToCanvas(point) {
  const rect = getContentRect();
  const videoWidth = state.currentVideo?.metadata?.width || 1;
  const videoHeight = state.currentVideo?.metadata?.height || 1;
  return {
    x: rect.left + (point.x / Math.max(1, videoWidth - 1)) * rect.width,
    y: rect.top + (point.y / Math.max(1, videoHeight - 1)) * rect.height,
  };
}

function canvasToPoint(x, y) {
  const rect = getContentRect();
  const clampedX = Math.min(Math.max(x, rect.left), rect.left + rect.width);
  const clampedY = Math.min(Math.max(y, rect.top), rect.top + rect.height);
  const videoWidth = state.currentVideo?.metadata?.width || 1;
  const videoHeight = state.currentVideo?.metadata?.height || 1;
  return {
    x: Math.round(((clampedX - rect.left) / Math.max(1, rect.width)) * (videoWidth - 1)),
    y: Math.round(((clampedY - rect.top) / Math.max(1, rect.height)) * (videoHeight - 1)),
  };
}

function isInsideContent(x, y) {
  const rect = getContentRect();
  return x >= rect.left && y >= rect.top && x <= rect.left + rect.width && y <= rect.top + rect.height;
}

function drawRoiOverlay() {
  const canvas = elements.roiCanvas;
  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  const contentRect = getContentRect();
  if (contentRect.width <= 0 || contentRect.height <= 0) {
    return;
  }
  context.strokeStyle = "#3ddc97";
  context.lineWidth = 2;
  drawPointSet(context, state.roiPoints, true, "#3ddc97");
  if (state.roiMode) {
    drawPointSet(context, state.pendingRoiPoints, false, "#ffd166");
  }
}

function drawPointSet(context, points, closePath, color) {
  if (!points.length) {
    return;
  }
  const canvasPoints = points.map(pointToCanvas);
  context.strokeStyle = color;
  context.fillStyle = color;
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(canvasPoints[0].x, canvasPoints[0].y);
  for (const point of canvasPoints.slice(1)) {
    context.lineTo(point.x, point.y);
  }
  if (closePath && canvasPoints.length === 4) {
    context.closePath();
  }
  context.stroke();

  canvasPoints.forEach((point, index) => {
    context.beginPath();
    context.arc(point.x, point.y, 5, 0, Math.PI * 2);
    context.fill();
    context.fillText(`P${index + 1}`, point.x + 8, point.y - 8);
  });
}

function cross(o, a, b) {
  return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
}

function isConvexQuad(points) {
  if (points.length !== 4) {
    return false;
  }
  const unique = new Set(points.map((point) => `${point.x},${point.y}`));
  if (unique.size !== 4) {
    return false;
  }
  const signs = [];
  for (let index = 0; index < 4; index += 1) {
    const value = cross(points[index], points[(index + 1) % 4], points[(index + 2) % 4]);
    if (value === 0) {
      return false;
    }
    signs.push(Math.sign(value));
  }
  return signs.every((sign) => sign === signs[0]);
}

function toggleRoiMode() {
  if (!state.currentVideo) {
    return;
  }
  state.roiMode = !state.roiMode;
  state.pendingRoiPoints = [];
  elements.videoPlayer.pause();
  elements.roiPolyButton.classList.toggle("is-active", state.roiMode);
  setStatus(
    elements.recordStatus,
    state.roiMode ? "请在视频区域依次点击 4 个点，形成凸四边形 ROI。" : "ROIpoly 已取消。",
  );
  drawRoiOverlay();
}

function handleCanvasClick(event) {
  if (!state.currentVideo || !state.roiMode) {
    return;
  }
  const rect = elements.roiCanvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  if (!isInsideContent(x, y)) {
    return;
  }
  state.pendingRoiPoints.push(canvasToPoint(x, y));
  if (state.pendingRoiPoints.length === 4) {
    if (!isConvexQuad(state.pendingRoiPoints)) {
      setStatus(elements.recordStatus, "ROI 无效：4 个点必须依次连接成凸四边形。", true);
      state.pendingRoiPoints = [];
    } else {
      state.roiPoints = [...state.pendingRoiPoints];
      state.pendingRoiPoints = [];
      state.roiMode = false;
      elements.roiPolyButton.classList.remove("is-active");
      setStatus(elements.recordStatus, "ROIpoly 已设置，可点击“记录”。");
      updateRoiInfo();
    }
  }
  drawRoiOverlay();
}

function updateRoiInfo() {
  if (!state.currentVideo) {
    elements.roiInfo.textContent = "未加载视频";
    return;
  }
  if (state.roiPoints.length !== 4) {
    elements.roiInfo.textContent = "未设置";
    return;
  }
  elements.roiInfo.textContent = state.roiPoints
    .map((point, index) => `P${index + 1}=(${point.x}, ${point.y})`)
    .join(" ");
}

async function recordCurrentFrame() {
  if (!state.currentVideo) {
    return;
  }
  if (state.roiPoints.length !== 4) {
    setStatus(elements.recordStatus, "请先设置 ROIpoly。", true);
    return;
  }
  const outputDir = elements.outputDir.value.trim();
  if (!outputDir) {
    setStatus(elements.recordStatus, "请先填写保存目录。", true);
    return;
  }

  try {
    const payload = await apiJson("/api/annotations/record", {
      method: "POST",
      body: JSON.stringify({
        video_id: state.currentVideo.id,
        frame_id: currentFrameId(),
        roi_points: state.roiPoints,
        output_dir: outputDir,
        current_time: elements.videoPlayer.currentTime,
      }),
    });
    state.annotation.records = [...(state.annotation.records || []), payload.record];
    state.annotation.output_dir = outputDir;
    state.unsaved = true;
    updateRecordsPreview();
    setStatus(elements.recordStatus, `已记录 ${payload.record_count} 条，autosave: ${payload.autosave_path}`);
  } catch (error) {
    setStatus(elements.recordStatus, `记录失败: ${error.message}`, true);
  }
}

async function saveAnnotations() {
  if (!state.currentVideo) {
    return;
  }
  try {
    const payload = await apiJson("/api/annotations/save", {
      method: "POST",
      body: JSON.stringify({ video_id: state.currentVideo.id }),
    });
    state.unsaved = false;
    setStatus(elements.recordStatus, `已保存 ${payload.record_count} 条到 ${payload.json_path}`);
  } catch (error) {
    setStatus(elements.recordStatus, `保存失败: ${error.message}`, true);
  }
}

async function exportAnnotationImages() {
  if (!state.currentVideo) {
    return;
  }
  elements.exportImagesButton.disabled = true;
  try {
    setStatus(elements.recordStatus, "正在保存 JSON 并导出图片…");
    const payload = await apiJson("/api/annotations/export-images", {
      method: "POST",
      body: JSON.stringify({ video_id: state.currentVideo.id }),
    });
    state.unsaved = false;
    const failed = payload.errors?.length ? `，${payload.errors.length} 条失败` : "";
    setStatus(
      elements.recordStatus,
      `已写入 ${payload.json_path}；导出 ${payload.exported_count} 张 PNG${failed}。`,
    );
    if (payload.errors?.length) {
      console.warn("export-images errors", payload.errors);
    }
  } catch (error) {
    setStatus(elements.recordStatus, `导出失败: ${error.message}`, true);
  } finally {
    elements.exportImagesButton.disabled = false;
  }
}

function updateRecordsPreview() {
  elements.recordsPreview.textContent = JSON.stringify(state.annotation.records || [], null, 2);
}

function useDefaultOutputDir() {
  if (state.currentVideo) {
    elements.outputDir.value = state.currentVideo.default_output_dir;
  }
}

function bindEvents() {
  elements.uploadButton.addEventListener("click", uploadSelectedFile);
  elements.refreshButton.addEventListener("click", () => refreshVideos().catch((error) => setStatus(elements.videoInfo, error.message, true)));
  elements.videoSelect.addEventListener("change", () => prefetchAnnotationsForSelectedVideo().catch(() => undefined));
  elements.loadButton.addEventListener("click", () => loadSelectedVideo().catch((error) => setStatus(elements.videoInfo, error.message, true)));
  elements.playButton.addEventListener("click", togglePlayPause);
  elements.prevButton.addEventListener("click", () => stepFrame(-1));
  elements.nextButton.addEventListener("click", () => stepFrame(1));
  elements.roiPolyButton.addEventListener("click", toggleRoiMode);
  elements.recordButton.addEventListener("click", recordCurrentFrame);
  elements.saveButton.addEventListener("click", saveAnnotations);
  elements.exportImagesButton.addEventListener("click", exportAnnotationImages);
  elements.defaultDirButton.addEventListener("click", useDefaultOutputDir);
  elements.seekSlider.addEventListener("input", seekToSlider);
  elements.roiCanvas.addEventListener("click", handleCanvasClick);
  elements.videoPlayer.addEventListener("play", () => {
    elements.playButton.textContent = "暂停";
  });
  elements.videoPlayer.addEventListener("pause", () => {
    elements.playButton.textContent = "播放";
  });
  elements.videoPlayer.addEventListener("loadedmetadata", () => {
    if (!state.roiPoints.length) {
      state.roiPoints = fullFrameRoiPoints();
      updateRoiInfo();
    }
    updateTimeline();
    resizeCanvas();
  });
  elements.videoPlayer.addEventListener("timeupdate", updateTimeline);
  elements.videoPlayer.addEventListener("seeked", updateTimeline);
  window.addEventListener("resize", resizeCanvas);
  window.addEventListener("keydown", (event) => {
    if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement?.tagName || "")) {
      return;
    }
    if (event.code === "Space") {
      event.preventDefault();
      togglePlayPause();
    } else if (event.code === "ArrowLeft") {
      event.preventDefault();
      stepFrame(-1);
    } else if (event.code === "ArrowRight") {
      event.preventDefault();
      stepFrame(1);
    }
  });
  window.addEventListener("pagehide", () => {
    if (!state.currentVideo || !state.unsaved) {
      return;
    }
    const body = JSON.stringify({ video_id: state.currentVideo.id });
    const blob = new Blob([body], { type: "application/json" });
    if (navigator.sendBeacon) {
      navigator.sendBeacon("/api/annotations/save", blob);
    } else {
      fetch("/api/annotations/save", {
        method: "POST",
        body,
        headers: { "Content-Type": "application/json" },
        keepalive: true,
      }).catch(() => undefined);
    }
  });
}

bindEvents();
resizeCanvas();
refreshVideos().catch((error) => setStatus(elements.videoInfo, error.message, true));
