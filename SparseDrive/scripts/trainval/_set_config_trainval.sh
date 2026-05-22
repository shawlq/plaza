#!/usr/bin/env bash
# 将 stage1/stage2 配置切换为 version=trainval（训练/评测前执行一次）
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

_set_one() {
    local cfg="$1"
    if grep -qE "^version = 'trainval'" "${cfg}"; then
        echo "[skip] 已是 trainval: ${cfg}"
        return 0
    fi
    if [[ ! -f "${cfg}.bak.trainval" ]]; then
        cp "${cfg}" "${cfg}.bak.trainval"
        echo "[backup] ${cfg}.bak.trainval"
    fi
    sed -i \
        -e "s/^version = 'mini'.*/# version = 'mini'  # disabled by scripts\/trainval/" \
        -e "s/^# version = 'trainval'.*/version = 'trainval'/" \
        "${cfg}"
    echo "[OK] ${cfg} -> version = 'trainval'"
}

for stage in 1 2; do
    _set_one "${SPARSEDRIVE_ROOT}/projects/configs/sparsedrive_small_stage${stage}.py"
done

echo "[OK] 配置已切换为 trainval。恢复 mini 可: bash scripts/trainval/_restore_config_mini.sh"
