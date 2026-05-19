#!/usr/bin/env bash
# =============================================================================
# 手动填写保存路径（仅需改本文件）
# =============================================================================

# OPENSCENE 数据根目录（脚本会自动创建 navsim_logs/mini、sensor_blobs/mini、maps）
MINI_DATA_ROOT="/home/c62664/workdir/gitcode/plaza/SparseDriveV2/data"

# OpenScene mini / 地图压缩包下载与解压目录
MINI_DOWNLOAD_DIR="/media/c62664/DATA/open/SparseDriveV2"

# Conda 环境名（00_setup_env.sh 会按 environment.yml 创建并安装依赖）
# 使用已有环境 sparsev2（若希望新建官方 navsim 环境，改回 MINI_CONDA_ENV="navsim"）
MINI_CONDA_ENV="${MINI_CONDA_ENV:-navsim}"

# =============================================================================
# 以下一般无需修改
# =============================================================================

_MINI_CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export MINI_REPO_ROOT="$(cd "${_MINI_CONFIG_DIR}/../.." && pwd)"
export MINI_EXP_ROOT="${MINI_REPO_ROOT}/exp"
export MINI_CONDA_ENV
