#!/usr/bin/env bash
# 由 scripts/mini/config.sh 提供 MINI_CONDA_ENV；在 mini 脚本中 source 后调用 activate_mini_conda。

activate_mini_conda() {
    local env_name="${MINI_CONDA_ENV:-}"
    if [[ -z "${env_name}" ]]; then
        return 0
    fi
    if [[ "${CONDA_DEFAULT_ENV:-}" == "${env_name}" ]]; then
        return 0
    fi
    if ! command -v conda >/dev/null 2>&1; then
        echo "错误: config.sh 设置了 MINI_CONDA_ENV=${env_name}，但未找到 conda" >&2
        exit 1
    fi
    # shellcheck source=/dev/null
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "${env_name}"
}
