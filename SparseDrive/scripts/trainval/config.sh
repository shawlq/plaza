#!/usr/bin/env bash
# =============================================================================
# 手动填写路径（仅需改本文件）
# =============================================================================

# nuScenes 归档下载目录（.tgz / .zip 存放处）
TRAINVAL_DOWNLOAD_DIR="${TRAINVAL_DOWNLOAD_DIR:-/your/path/sparsedrive/archives}"

# 解压后的 nuscenes 根目录（含 v1.0-trainval、can_bus、maps）
TRAINVAL_NUSCENES_ROOT="${TRAINVAL_NUSCENES_ROOT:-${TRAINVAL_DOWNLOAD_DIR}/nuscenes}"

# Conda 环境名（与 mini 可共用同一环境）
TRAINVAL_CONDA_ENV="${TRAINVAL_CONDA_ENV:-sparsedrive}"

# =============================================================================
# 以下一般无需修改
# =============================================================================

_TRAINVAL_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TRAINVAL_REPO_ROOT="$(cd "${_TRAINVAL_CONFIG_DIR}/../.." && pwd)"
export TRAINVAL_DOWNLOAD_DIR
export TRAINVAL_NUSCENES_ROOT
export TRAINVAL_CONDA_ENV
