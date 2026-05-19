#!/usr/bin/env bash
# 各 mini 脚本 source 此文件；可在同目录 env.local.sh 覆盖路径。
set -euo pipefail

_MINI_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export NAVSIM_DEVKIT_ROOT="${NAVSIM_DEVKIT_ROOT:-$(cd "${_MINI_SCRIPT_DIR}/../.." && pwd)}"
export NAVSIM_EXP_ROOT="${NAVSIM_EXP_ROOT:-${NAVSIM_DEVKIT_ROOT}/exp}"

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

: "${OPENSCENE_DATA_ROOT:?请设置 OPENSCENE_DATA_ROOT（或在 scripts/mini/env.local.sh 中设置）}"
: "${NUPLAN_MAPS_ROOT:?请设置 NUPLAN_MAPS_ROOT（或在 scripts/mini/env.local.sh 中设置）}"

_NAVMINI_LOGS="${OPENSCENE_DATA_ROOT}/navsim_logs/mini"
if [[ "${OPENSCENE_DATA_ROOT}" == *"/path/to/"* ]] || [[ ! -d "${_NAVMINI_LOGS}" ]]; then
    echo "错误: OPENSCENE_DATA_ROOT 无效或缺少 navsim_logs/mini" >&2
    echo "  当前 OPENSCENE_DATA_ROOT=${OPENSCENE_DATA_ROOT}" >&2
    echo "  期望存在: ${_NAVMINI_LOGS}" >&2
    echo "  请编辑 scripts/mini/env.local.sh（可参考 env.local.sh.example）" >&2
    exit 1
fi

export HYDRA_FULL_ERROR=1
export DATA_CACHE_NAVMINI="${NAVSIM_EXP_ROOT}/data_cache_navmini"
export METRIC_CACHE_NAVMINI_V1="${NAVSIM_EXP_ROOT}/metric_cache_navminiv1"

# 以绝对路径运行 planning/script/*.py 时，Python 不会把仓库根加入 sys.path
export PYTHONPATH="${NAVSIM_DEVKIT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

cd "${NAVSIM_DEVKIT_ROOT}"
