#!/usr/bin/env bash
# 各 trainval 脚本 source 此文件
set -euo pipefail

_TRAINVAL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SPARSEDRIVE_ROOT="${SPARSEDRIVE_ROOT:-$(cd "${_TRAINVAL_SCRIPT_DIR}/../.." && pwd)}"

if [[ -f "${_TRAINVAL_SCRIPT_DIR}/config.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_TRAINVAL_SCRIPT_DIR}/config.sh"
fi

# 与 mini 共用 env.local.sh（00_setup 写入的是 MINI_* 变量）
_MINI_ENV_LOCAL="${SPARSEDRIVE_ROOT}/scripts/mini/env.local.sh"
if [[ -f "${_MINI_ENV_LOCAL}" ]]; then
    # shellcheck source=/dev/null
    source "${_MINI_ENV_LOCAL}"
fi

if [[ -f "${SPARSEDRIVE_ROOT}/scripts/mini/_conda.sh" ]]; then
    export MINI_CONDA_ENV="${TRAINVAL_CONDA_ENV}"
    # shellcheck source=/dev/null
    source "${SPARSEDRIVE_ROOT}/scripts/mini/_conda.sh"
    activate_mini_conda
fi

: "${TRAINVAL_NUSCENES_ROOT:?请设置 TRAINVAL_NUSCENES_ROOT（编辑 scripts/trainval/config.sh）}"

export PYTHONPATH="${SPARSEDRIVE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="${CONDA_PREFIX:-}/lib:${LD_LIBRARY_PATH:-}"

cd "${SPARSEDRIVE_ROOT}"
