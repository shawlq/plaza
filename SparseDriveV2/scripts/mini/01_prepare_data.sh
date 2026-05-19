#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "${_SCRIPT_DIR}/config.sh"
# shellcheck source=_conda.sh
source "${_SCRIPT_DIR}/_conda.sh"
# shellcheck source=_install_deps.sh
source "${_SCRIPT_DIR}/_install_deps.sh"
activate_mini_conda
if ! python -c "import torch" >/dev/null 2>&1; then
    echo "错误: 当前 Python 无 torch。请先执行: bash scripts/mini/00_setup_env.sh" >&2
    exit 1
fi

# shellcheck source=../../download/fetch_common.sh
source "${MINI_REPO_ROOT}/download/fetch_common.sh"

echo "========== 1/4 OpenScene mini 下载 =========="
(
    cd "${MINI_DOWNLOAD_DIR}"
    bash "${MINI_REPO_ROOT}/download/download_mini.sh"
)

echo "========== 2/4 OpenScene mini 解压 =========="
(
    cd "${MINI_DOWNLOAD_DIR}"
    bash "${MINI_REPO_ROOT}/download/download_mini.sh" --extract
)

echo "========== 3/4 nuPlan 地图 =========="
(
    cd "${MINI_DOWNLOAD_DIR}"
    MAP_ZIP="nuplan-maps-v1.1.zip"
    if [[ -d "${MINI_DATA_ROOT}/maps" ]]; then
        echo "[跳过] maps 已存在于 MINI_DATA_ROOT"
    elif [[ ! -d maps ]]; then
        if [[ ! -f "${MAP_ZIP}" ]]; then
            fetch_resume \
                "https://motional-nuplan.s3-ap-northeast-1.amazonaws.com/public/nuplan-v1.1/nuplan-maps-v1.1.zip" \
                "${MAP_ZIP}"
        fi
        unzip -q "${MAP_ZIP}"
        mv nuplan-maps-v1.0 maps
        mkdir -p "${MINI_DATA_ROOT}"
        mv maps "${MINI_DATA_ROOT}/maps"
    else
        mkdir -p "${MINI_DATA_ROOT}"
        mv maps "${MINI_DATA_ROOT}/maps"
    fi
)

echo "========== 4/4 模型权重与 anchor =========="
mkdir -p "${MINI_REPO_ROOT}/ckpt/kmeans"
(
    cd "${MINI_REPO_ROOT}/ckpt"
    if [[ ! -f resnet34.bin ]]; then
        fetch_resume \
            "https://huggingface.co/timm/resnet34.a1_in1k/resolve/main/pytorch_model.bin" \
            resnet34.bin
    fi
)
(
    cd "${MINI_REPO_ROOT}/ckpt/kmeans"
    for f in path_1024.npy velocity_256.npy trajectory_1024_256.npz; do
        if [[ ! -f "${f}" ]]; then
            fetch_resume \
                "https://huggingface.co/wenchaosun/SparseDriveV2/resolve/main/${f}" \
                "${f}"
        fi
    done
)

install_sparsedrive_ops

bash "${_SCRIPT_DIR}/00_setup_env.sh" --link --skip-deps

echo "[OK] 01_prepare_data 完成"
