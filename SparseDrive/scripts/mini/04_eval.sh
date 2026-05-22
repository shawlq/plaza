#!/usr/bin/env bash
# 用法:
#   bash scripts/mini/04_eval.sh
#   CHECKPOINT=ckpt/sparsedrive_stage2.pth bash scripts/mini/04_eval.sh
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

CONFIG="projects/configs/sparsedrive_small_stage2.py"
RESULT_PKL="work_dirs/sparsedrive_small_stage2/results.pkl"

if [[ -z "${CHECKPOINT:-}" ]]; then
    if [[ -f ckpt/sparsedrive_stage2.pth ]]; then
        CHECKPOINT="ckpt/sparsedrive_stage2.pth"
    else
        CHECKPOINT="$(find work_dirs/sparsedrive_small_stage2 -name 'epoch_*.pth' 2>/dev/null | sort -V | tail -n 1 || true)"
    fi
fi
if [[ -z "${CHECKPOINT}" || ! -f "${CHECKPOINT}" ]]; then
    echo "未找到 checkpoint，请先训练或设置 CHECKPOINT=..." >&2
    exit 1
fi

echo "CHECKPOINT=${CHECKPOINT}"

bash ./tools/dist_test.sh \
    "${CONFIG}" \
    "${CHECKPOINT}" \
    1 \
    --deterministic \
    --eval bbox \
    --out "${RESULT_PKL}"

echo "[OK] 04_eval 完成"
echo "  指标: 见终端输出"
echo "  预测: ${RESULT_PKL}"
