#!/usr/bin/env bash
# 解压 trainval、生成 infos pkl、kmeans anchor、下载 ResNet50；编译 ops
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

_MINI_INSTALL="${SPARSEDRIVE_ROOT}/scripts/mini/_install_deps.sh"
if [[ -f "${_MINI_INSTALL}" ]]; then
    export MINI_CONDA_ENV="${TRAINVAL_CONDA_ENV}"
    # shellcheck source=/dev/null
    source "${_MINI_INSTALL}"
fi

DOWNLOAD="${TRAINVAL_DOWNLOAD_DIR}"
NUSC="${TRAINVAL_NUSCENES_ROOT}"

mkdir -p "${NUSC}" "${NUSC}/maps" "${SPARSEDRIVE_ROOT}/data/infos" \
    "${SPARSEDRIVE_ROOT}/data/kmeans" "${SPARSEDRIVE_ROOT}/vis/kmeans" \
    "${SPARSEDRIVE_ROOT}/ckpt"

_extract_if_needed() {
    local archive="$1"
    local marker="$2"
    local cmd="$3"
    if [[ -e "${marker}" ]]; then
        echo "[skip] 已解压: ${marker}"
        return 0
    fi
    if [[ ! -f "${DOWNLOAD}/${archive}" ]]; then
        echo "错误: 缺少 ${DOWNLOAD}/${archive}，请先 bash scripts/trainval/01_download_data.sh" >&2
        exit 1
    fi
    echo "[extract] ${archive} -> ${NUSC}"
    eval "${cmd}"
}

echo "========== 1/5 解压 can_bus / 地图 / trainval 分卷（耗时很长，可 nohup 后台跑）=========="
_extract_if_needed "can_bus.zip" "${NUSC}/can_bus" \
    "unzip -q -o '${DOWNLOAD}/can_bus.zip' -d '${NUSC}'"

_extract_if_needed "nuScenes-map-expansion-v1.3.zip" "${NUSC}/maps/expansion" \
    "unzip -q -o '${DOWNLOAD}/nuScenes-map-expansion-v1.3.zip' -d '${NUSC}/maps'"

_extract_if_needed "v1.0-trainval_meta.tgz" "${NUSC}/v1.0-trainval" \
    "tar -xzf '${DOWNLOAD}/v1.0-trainval_meta.tgz' -C '${NUSC}'"

TRAINVAL_ARCHIVES=()
for i in $(seq -w 1 10); do
    TRAINVAL_ARCHIVES+=(
        "v1.0-trainval${i}_blobs.tgz"
        "v1.0-trainval${i}_blobs_camera.tgz"
        "v1.0-trainval${i}_blobs_lidar.tgz"
        "v1.0-trainval${i}_blobs_radar.tgz"
        "v1.0-trainval${i}_keyframes.tgz"
    )
done

for archive in "${TRAINVAL_ARCHIVES[@]}"; do
    marker="${NUSC}/.extracted_${archive}"
    if [[ -f "${marker}" ]]; then
        echo "[skip] 已解压: ${archive}"
        continue
    fi
    if [[ ! -f "${DOWNLOAD}/${archive}" ]]; then
        echo "错误: 缺少 ${DOWNLOAD}/${archive}" >&2
        exit 1
    fi
    echo "[extract] ${archive} -> ${NUSC}"
    tar -xzf "${DOWNLOAD}/${archive}" -C "${NUSC}"
    touch "${marker}"
done

ln -sfn "${NUSC}" "${SPARSEDRIVE_ROOT}/data/nuscenes"

echo "========== 2/5 生成 data/infos/*.pkl（v1.0 trainval）=========="
if [[ -f "${SPARSEDRIVE_ROOT}/data/infos/nuscenes_infos_train.pkl" ]]; then
    echo "[skip] infos 已存在"
else
    python "${SPARSEDRIVE_ROOT}/tools/data_converter/nuscenes_converter.py" nuscenes \
        --root-path "${SPARSEDRIVE_ROOT}/data/nuscenes" \
        --canbus "${SPARSEDRIVE_ROOT}/data/nuscenes" \
        --out-dir "${SPARSEDRIVE_ROOT}/data/infos/" \
        --extra-tag nuscenes \
        --version v1.0
fi

echo "========== 3/5 K-means anchors =========="
if [[ -f "${SPARSEDRIVE_ROOT}/data/kmeans/kmeans_plan_6.npy" ]]; then
    echo "[skip] kmeans 已存在"
else
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_det.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_map.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_motion.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_plan.py"
fi

echo "========== 4/5 预训练 backbone =========="
RESNET="${SPARSEDRIVE_ROOT}/ckpt/resnet50-19c8e357.pth"
if [[ -f "${RESNET}" ]]; then
    echo "[skip] ${RESNET}"
else
    if command -v wget >/dev/null 2>&1; then
        wget -q https://download.pytorch.org/models/resnet50-19c8e357.pth -O "${RESNET}"
    else
        python -c "
import urllib.request
urllib.request.urlretrieve(
    'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    '${RESNET}')
"
    fi
fi

echo "========== 5/5 编译 deformable_aggregation ops =========="
if declare -f install_sparsedrive_ops >/dev/null 2>&1; then
    install_sparsedrive_ops
else
    pushd "${SPARSEDRIVE_ROOT}/projects/mmdet3d_plugin/ops" >/dev/null
    python setup.py develop
    popd >/dev/null
fi

echo "[OK] 02_prepare_data 完成"
