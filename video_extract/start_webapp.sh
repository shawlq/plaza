#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="${SCRIPT_DIR}/.webapp_uvicorn.pid"
LOG_FILE="${SCRIPT_DIR}/webapp.log"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8100}"

is_running_pid() {
  local pid="$1"
  [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

start_webapp() {
  if [[ -f "$PID_FILE" ]]; then
    local existing
    existing="$(cat "$PID_FILE" || true)"
    if is_running_pid "$existing"; then
      echo "WebApp 已在运行 (PID ${existing}). 使用: $0 stop"
      exit 1
    fi
    rm -f "$PID_FILE"
  fi

  nohup python -m uvicorn webapp.app:app --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  echo "已启动 PID $(cat "$PID_FILE")，日志追加到 ${LOG_FILE}，监听 ${HOST}:${PORT}"
}

stop_webapp() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "未发现 PID 文件，视为未启动。"
    exit 0
  fi
  local pid
  pid="$(cat "$PID_FILE" || true)"
  rm -f "$PID_FILE"

  if ! is_running_pid "$pid"; then
    echo "进程 ${pid} 未在运行。"
    exit 0
  fi

  kill "$pid" || true
  echo "已向 PID ${pid} 发送 SIGTERM。"
}

status_webapp() {
  if [[ ! -f "$PID_FILE" ]]; then
    echo "状态: 未运行（无 PID 文件）"
    echo "日志文件: ${LOG_FILE}"
    return 0
  fi

  local pid
  pid="$(cat "$PID_FILE" || true)"
  if ! is_running_pid "$pid"; then
    echo "状态: 未运行（PID 文件中的进程 ${pid} 已失效，可删掉 ${PID_FILE}）"
    echo "日志文件: ${LOG_FILE}"
    return 0
  fi

  echo "状态: 运行中"
  echo "PID: ${pid}"
  echo "监听: ${HOST}:${PORT}（以启动时环境变量为准；详见下方进程命令行）"
  if [[ -r "/proc/${pid}/cmdline" ]]; then
    echo -n "命令行: "
    tr '\0' ' ' </proc/${pid}/cmdline || true
    echo
  fi
  if [[ -f "$LOG_FILE" ]]; then
    echo "日志文件: ${LOG_FILE}（$(wc -l <"$LOG_FILE" 2>/dev/null || echo '?') 行）"
  else
    echo "日志文件: ${LOG_FILE}（尚未创建）"
  fi
}

show_logs() {
  if [[ "${1:-}" == "-h" ]] || [[ "${1:-}" == "--help" ]]; then
    echo "用法: $0 logs [-f]"
    echo "  无参数 — 默认输出日志末尾若干行（与 tail -n 保持一致行数）"
    echo "  -f     — 持续跟踪新日志（同 tail -f）"
    exit 0
  fi

  if [[ ! -f "$LOG_FILE" ]]; then
    echo "暂无日志文件: ${LOG_FILE}"
    exit 0
  fi

  if [[ "${1:-}" == "-f" ]]; then
    if [[ $# -gt 1 ]]; then
      echo "用法: $0 logs [-f]"
      exit 1
    fi
    tail -f "$LOG_FILE"
    return
  fi

  if [[ $# -gt 0 ]]; then
    echo "用法: $0 logs [-f]"
    exit 1
  fi

  tail -n 400 "$LOG_FILE"
}

ACTION="${1:-start}"
case "$ACTION" in
start | '') start_webapp ;;
stop) stop_webapp ;;
status) status_webapp ;;
logs)
  shift
  show_logs "$@"
  ;;
*)
  echo "用法: $0 [start|stop|status|logs]"
  echo "  无参数或 start — 后台启动 uvicorn（PID 写入 ${PID_FILE}）"
  echo "  stop            — 根据 PID 文件停止服务"
  echo "  status          — 查看运行状态"
  echo "  logs            — 查看日志末尾"
  echo "  logs -f         — 持续跟踪日志（tail -f）"
  exit 1
  ;;
esac
