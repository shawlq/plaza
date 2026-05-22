#!/usr/bin/env bash
# 用法:
#   bash scripts/mini/05_visualize.sh
#   RESULT_PKL=work_dirs/sparsedrive_small_stage2/results.pkl bash scripts/mini/05_visualize.sh
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

CONFIG="projects/configs/sparsedrive_small_stage2.py"
RESULT_PKL="${RESULT_PKL:-work_dirs/sparsedrive_small_stage2/results.pkl}"
OUT_DIR="${OUT_DIR:-vis/mini}"

if [[ ! -f "${RESULT_PKL}" ]]; then
    echo "缺少 ${RESULT_PKL}，请先: bash scripts/mini/04_eval.sh" >&2
    exit 1
fi

python tools/visualization/visualize.py \
    "${CONFIG}" \
    --result-path "${RESULT_PKL}" \
    --out-dir "${OUT_DIR}"

echo "[OK] 05_visualize 完成"
echo "  输出目录: ${OUT_DIR}/"
echo "  合成视频: ${OUT_DIR}/combine/"
