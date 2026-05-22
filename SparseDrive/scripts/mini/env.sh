#!/usr/bin/env bash
# 各 mini 脚本 source 此文件
set -euo pipefail

_MINI_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SPARSEDRIVE_ROOT="${SPARSEDRIVE_ROOT:-$(cd "${_MINI_SCRIPT_DIR}/../.." && pwd)}"

if [[ -f "${_MINI_SCRIPT_DIR}/config.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_MINI_SCRIPT_DIR}/config.sh"
fi

if [[ -f "${_MINI_SCRIPT_DIR}/env.local.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_MINI_SCRIPT_DIR}/env.local.sh"
fi

if [[ -f "${_MINI_SCRIPT_DIR}/_conda.sh" ]]; then
    # shellcheck source=/dev/null
    source "${_MINI_SCRIPT_DIR}/_conda.sh"
    activate_mini_conda
fi

: "${MINI_NUSCENES_ROOT:?请设置 MINI_NUSCENES_ROOT（编辑 scripts/mini/config.sh）}"

export PYTHONPATH="${SPARSEDRIVE_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
export LD_LIBRARY_PATH="${CONDA_PREFIX:-}/lib:${LD_LIBRARY_PATH:-}"

cd "${SPARSEDRIVE_ROOT}"
