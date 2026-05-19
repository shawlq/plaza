#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "${_SCRIPT_DIR}/config.sh"
# shellcheck source=_conda.sh
source "${_SCRIPT_DIR}/_conda.sh"
# shellcheck source=_install_deps.sh
source "${_SCRIPT_DIR}/_install_deps.sh"

_LINK_ONLY=false
_SKIP_DEPS=false
for arg in "$@"; do
    case "${arg}" in
        --link) _LINK_ONLY=true ;;
        --skip-deps) _SKIP_DEPS=true ;;
        *)
            echo "未知参数: ${arg}（可选: --link, --skip-deps）" >&2
            exit 1
            ;;
    esac
done

if [[ -z "${MINI_DATA_ROOT}" || -z "${MINI_DOWNLOAD_DIR}" ]]; then
    echo "请编辑 scripts/mini/config.sh，填写 MINI_DATA_ROOT 与 MINI_DOWNLOAD_DIR" >&2
    exit 1
fi

mkdir -p "${MINI_DATA_ROOT}/navsim_logs" "${MINI_DATA_ROOT}/sensor_blobs"
mkdir -p "${MINI_DOWNLOAD_DIR}" "${MINI_EXP_ROOT}"

if [[ "${_LINK_ONLY}" == false && "${_SKIP_DEPS}" == false ]]; then
    install_mini_all_deps
    # hydra-core 1.2.0 在 Python 3.11 会因 dataclass mutable default 无法 import。
    # requirements-mini.lock.txt 已 pin 1.3.2，但 nuplan-devkit 可能将其降回 1.2.0，故最后再固定一次。
    activate_mini_conda
    echo "========== 固定 hydra-core (Python 3.11 兼容) =========="
    python -m pip install -q "hydra-core==1.3.2"
    python -c "import hydra; from hydra.utils import instantiate"
    echo "[OK] hydra-core $(python -m pip show hydra-core | awk -F': ' '/^Version:/{print $2}')"
elif [[ "${_LINK_ONLY}" == false ]]; then
    # --skip-deps：仍确保 navsim 可 import（常见：复用已有 conda 环境）
    activate_mini_conda
    if ! python -c "import navsim" >/dev/null 2>&1; then
        install_navsim_package
    else
        echo "[OK] navsim 已可 import"
    fi
fi

_resolve_mini_subdir() {
    # OpenScene 解压后常见两种布局：直接是 log/scene 目录，或包在 mini/ 子目录下
    local base_dir="$1"
    if [[ -d "${base_dir}/mini" ]]; then
        echo "${base_dir}/mini"
    else
        echo "${base_dir}"
    fi
}

_link_data() {
    if [[ ! -d "${MINI_DOWNLOAD_DIR}/mini_navsim_logs" ]]; then
        echo "缺少 ${MINI_DOWNLOAD_DIR}/mini_navsim_logs，请先执行: bash scripts/mini/01_prepare_data.sh" >&2
        exit 1
    fi
    if [[ ! -d "${MINI_DOWNLOAD_DIR}/mini_sensor_blobs" ]]; then
        echo "缺少 ${MINI_DOWNLOAD_DIR}/mini_sensor_blobs，请先执行: bash scripts/mini/01_prepare_data.sh" >&2
        exit 1
    fi
    _navmini_logs="$(_resolve_mini_subdir "${MINI_DOWNLOAD_DIR}/mini_navsim_logs")"
    _navmini_sensors="$(_resolve_mini_subdir "${MINI_DOWNLOAD_DIR}/mini_sensor_blobs")"
    ln -sfn "${_navmini_logs}" "${MINI_DATA_ROOT}/navsim_logs/mini"
    ln -sfn "${_navmini_sensors}" "${MINI_DATA_ROOT}/sensor_blobs/mini"
    if [[ -d "${MINI_DATA_ROOT}/maps" ]]; then
        : # maps 已在 DATA_ROOT
    elif [[ -d "${MINI_DOWNLOAD_DIR}/maps" ]]; then
        ln -sfn "${MINI_DOWNLOAD_DIR}/maps" "${MINI_DATA_ROOT}/maps"
    else
        echo "缺少 maps，请先执行: bash scripts/mini/01_prepare_data.sh" >&2
        exit 1
    fi
}

cat > "${_SCRIPT_DIR}/env.local.sh" <<EOF
#!/usr/bin/env bash
# 由 scripts/mini/00_setup_env.sh 自动生成，请勿手改
export MINI_CONDA_ENV=${MINI_CONDA_ENV}
export OPENSCENE_DATA_ROOT=${MINI_DATA_ROOT}
export NUPLAN_MAPS_ROOT=${MINI_DATA_ROOT}/maps
export NAVSIM_EXP_ROOT=${MINI_EXP_ROOT}
EOF

export NAVSIM_DEVKIT_ROOT="${MINI_REPO_ROOT}"
export NAVSIM_EXP_ROOT="${MINI_EXP_ROOT}"
export OPENSCENE_DATA_ROOT="${MINI_DATA_ROOT}"
export NUPLAN_MAPS_ROOT="${MINI_DATA_ROOT}/maps"

echo "[OK] env.local.sh 已写入"
echo "  MINI_CONDA_ENV=${MINI_CONDA_ENV}"
echo "  OPENSCENE_DATA_ROOT=${OPENSCENE_DATA_ROOT}"
echo "  NUPLAN_MAPS_ROOT=${NUPLAN_MAPS_ROOT}"
echo "  NAVSIM_EXP_ROOT=${NAVSIM_EXP_ROOT}"
echo ""
echo "后续脚本请先: conda activate ${MINI_CONDA_ENV}"
echo "（或依赖 env.sh 自动 activate）"

if [[ "${_LINK_ONLY}" == true ]]; then
    _link_data
    echo "[OK] 软链接已创建"
elif [[ -d "${MINI_DOWNLOAD_DIR}/mini_navsim_logs" ]]; then
    _link_data
    echo "[OK] 软链接已创建"
fi
