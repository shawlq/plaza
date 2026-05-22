#!/usr/bin/env bash
# 从 Motional nuScenes 公开桶下载 mini 所需归档；已存在则跳过
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

BUCKET_PREFIX="s3://motional-nuscenes/public/v1.0"
REGION="ap-northeast-1"
DEST="${MINI_DOWNLOAD_DIR}"

# mini 训练/评测/可视化所需（不含 trainval 分卷）
FILES=(
    "can_bus.zip"
    "md5.checksum"
    "nuScenes-map-expansion-v1.3.zip"
    "v1.0-mini.tgz"
    "v1.0-test_blobs.tgz"
    "v1.0-test_blobs_camera.tgz"
    "v1.0-test_blobs_lidar.tgz"
    "v1.0-test_blobs_radar.tgz"
    "v1.0-test_meta.tgz"
)

if ! command -v aws >/dev/null 2>&1; then
    echo "错误: 需要 aws CLI。安装: pip install awscli 或 apt install awscli" >&2
    exit 1
fi

mkdir -p "${DEST}"

for name in "${FILES[@]}"; do
    dst="${DEST}/${name}"
    if [[ -f "${dst}" ]]; then
        echo "[skip] 已存在: ${dst}"
        continue
    fi
    echo "[get] ${name}"
    aws s3 cp --no-sign-request --region "${REGION}" \
        "${BUCKET_PREFIX}/${name}" "${dst}"
done

echo "[OK] 01_download_data 完成（共 ${#FILES[@]} 项已检查/下载）"
