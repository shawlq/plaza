#!/usr/bin/env bash
# SparseDriveV2 visualization (see tools/visualization/visualize.py)
#
# Usage:
#   bash scripts/visualize.sh
#   CHECKPOINT=exp/.../ep0010.ckpt MAX_SCENES=5 bash scripts/visualize.sh
#   bash scripts/visualize.sh --split mini --max-scenes 3 --no-video
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "${_SCRIPT_DIR}/.." && pwd)"
export PYTHONPATH="${_REPO_ROOT}:${PYTHONPATH:-}"

# Load paths (OPENSCENE_DATA_ROOT, NUPLAN_MAPS_ROOT, ...)
if [[ -f "${_REPO_ROOT}/set_env_val.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_REPO_ROOT}/set_env_val.sh"
fi
if [[ -f "${_SCRIPT_DIR}/mini/env.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_SCRIPT_DIR}/mini/env.sh"
fi

SPLIT="${SPLIT:-mini}"
SCENE_FILTER="${SCENE_FILTER:-navmini}"
MAX_SCENES="${MAX_SCENES:-5}"
OUT_DIR="${OUT_DIR:-vis/sparsedrive_${SCENE_FILTER}}"
CHECKPOINT="${CHECKPOINT:-}"
PREDICTIONS_PKL="${PREDICTIONS_PKL:-}"
DATASET_VERSION="${DATASET_VERSION:-v1}"

EXTRA_ARGS=("$@")
CMD=(
    python "${_REPO_ROOT}/tools/visualization/visualize.py"
    --split "${SPLIT}"
    --scene-filter "${SCENE_FILTER}"
    --max-scenes "${MAX_SCENES}"
    --out-dir "${OUT_DIR}"
    --frame-mode current
    --dataset-version "${DATASET_VERSION}"
)

if [[ -n "${CHECKPOINT}" ]]; then
    CMD+=(--checkpoint "${CHECKPOINT}")
fi
if [[ -n "${PREDICTIONS_PKL}" ]]; then
    CMD+=(--predictions-pkl "${PREDICTIONS_PKL}")
fi

"${CMD[@]}" "${EXTRA_ARGS[@]}"

echo "[OK] Visualization done -> ${OUT_DIR}/combine/ and ${OUT_DIR}/video.mp4"
