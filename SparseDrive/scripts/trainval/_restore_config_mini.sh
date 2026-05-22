#!/usr/bin/env bash
# 从 .bak.trainval 恢复 stage 配置（切回 mini 训练时使用）
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

for stage in 1 2; do
    cfg="${SPARSEDRIVE_ROOT}/projects/configs/sparsedrive_small_stage${stage}.py"
    bak="${cfg}.bak.trainval"
    if [[ -f "${bak}" ]]; then
        cp "${bak}" "${cfg}"
        echo "[OK] 已恢复: ${cfg}"
    else
        echo "[warn] 无备份 ${bak}，跳过"
    fi
done
