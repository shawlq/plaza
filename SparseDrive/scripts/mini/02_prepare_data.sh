#!/usr/bin/env bash
# 解压 mini 数据、生成 infos pkl、kmeans anchor、下载 ResNet50 预训练
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"
# shellcheck source=_install_deps.sh
source "${_SCRIPT_DIR}/_install_deps.sh"

DOWNLOAD="${MINI_DOWNLOAD_DIR}"
NUSC="${MINI_NUSCENES_ROOT}"

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
        echo "错误: 缺少 ${DOWNLOAD}/${archive}，请先 bash scripts/mini/01_download_data.sh" >&2
        exit 1
    fi
    echo "[extract] ${archive} -> ${NUSC}"
    eval "${cmd}"
}

echo "========== 1/4 解压 nuScenes mini =========="
_extract_if_needed "can_bus.zip" "${NUSC}/can_bus" \
    "unzip -q -o '${DOWNLOAD}/can_bus.zip' -d '${NUSC}'"

_extract_if_needed "v1.0-mini.tgz" "${NUSC}/v1.0-mini" \
    "tar -xzf '${DOWNLOAD}/v1.0-mini.tgz' -C '${NUSC}'"

_extract_if_needed "nuScenes-map-expansion-v1.3.zip" "${NUSC}/maps/expansion" \
    "unzip -q -o '${DOWNLOAD}/nuScenes-map-expansion-v1.3.zip' -d '${NUSC}/maps'"

ln -sfn "${NUSC}" "${SPARSEDRIVE_ROOT}/data/nuscenes"

echo "========== 2/4 生成 data/infos/mini/*.pkl =========="
if [[ -f "${SPARSEDRIVE_ROOT}/data/infos/mini/nuscenes_infos_train.pkl" ]]; then
    echo "[skip] infos 已存在"
else
    python "${SPARSEDRIVE_ROOT}/tools/data_converter/nuscenes_converter.py" nuscenes \
        --root-path "${SPARSEDRIVE_ROOT}/data/nuscenes" \
        --canbus "${SPARSEDRIVE_ROOT}/data/nuscenes" \
        --out-dir "${SPARSEDRIVE_ROOT}/data/infos/" \
        --extra-tag nuscenes \
        --version v1.0-mini
fi

# kmeans 脚本默认读取 data/infos/*.pkl，链到 mini 子目录
MINI_INFO="${SPARSEDRIVE_ROOT}/data/infos/mini"
for f in nuscenes_infos_train.pkl nuscenes_infos_val.pkl; do
    ln -sfn "${MINI_INFO}/${f}" "${SPARSEDRIVE_ROOT}/data/infos/${f}"
done

echo "========== 3/4 K-means anchors =========="
if [[ -f "${SPARSEDRIVE_ROOT}/data/kmeans/kmeans_plan_6.npy" ]]; then
    echo "[skip] kmeans 已存在"
else
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_det.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_map.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_motion.py"
    python "${SPARSEDRIVE_ROOT}/tools/kmeans/kmeans_plan.py"
fi

echo "========== 4/4 预训练 backbone =========="
RESNET="${SPARSEDRIVE_ROOT}/ckpt/resnet50-19c8e357.pth"
if [[ -f "${RESNET}" ]]; then
    echo "[skip] ${RESNET}"
else
    if command -v wget >/dev/null 2>&1; then
        wget -q https://download.pytorch.org/models/resnet50-19c8e357.pth -O "${RESNET}"
    else
        python -m pip install -q wget 2>/dev/null || true
        python -c "
import urllib.request
urllib.request.urlretrieve(
    'https://download.pytorch.org/models/resnet50-19c8e357.pth',
    '${RESNET}')
"
    fi
fi

install_sparsedrive_ops

echo "[OK] 02_prepare_data 完成"
