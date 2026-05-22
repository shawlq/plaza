#!/usr/bin/env bash
# =============================================================================
# 手动填写路径（仅需改本文件）
# =============================================================================

# nuScenes 归档下载目录（.tgz / .zip 存放处）
MINI_DOWNLOAD_DIR="${MINI_DOWNLOAD_DIR:-/media/c62664/DATA/open/sparsedrive/data}"

# 解压后的 nuscenes 根目录（含 v1.0-mini、can_bus、maps）
MINI_NUSCENES_ROOT="${MINI_NUSCENES_ROOT:-${MINI_DOWNLOAD_DIR}/nuscenes}"

# Conda 环境名（00_setup_env.sh 会创建/更新）
MINI_CONDA_ENV="${MINI_CONDA_ENV:-sparsedrive}"

# =============================================================================
# 以下一般无需修改
# =============================================================================

_MINI_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MINI_REPO_ROOT="$(cd "${_MINI_CONFIG_DIR}/../.." && pwd)"
export MINI_DOWNLOAD_DIR
export MINI_NUSCENES_ROOT
export MINI_CONDA_ENV
