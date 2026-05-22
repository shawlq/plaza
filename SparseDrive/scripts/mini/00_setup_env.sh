#!/usr/bin/env bash
# 创建/更新 conda 环境、安装依赖、编译 ops、写入 env.local.sh、创建 data/nuscenes 软链接
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=config.sh
source "${_SCRIPT_DIR}/config.sh"
# shellcheck source=_conda.sh
source "${_SCRIPT_DIR}/_conda.sh"
# shellcheck source=_install_deps.sh
source "${_SCRIPT_DIR}/_install_deps.sh"

_SKIP_DEPS=false
for arg in "$@"; do
    case "${arg}" in
        --skip-deps) _SKIP_DEPS=true ;;
        *)
            echo "未知参数: ${arg}（可选: --skip-deps）" >&2
            exit 1
            ;;
    esac
done

mkdir -p "${MINI_DOWNLOAD_DIR}" "${MINI_NUSCENES_ROOT}" "${MINI_REPO_ROOT}/data"

if [[ "${_SKIP_DEPS}" == false ]]; then
    install_mini_all_deps
fi

cat > "${_SCRIPT_DIR}/env.local.sh" <<EOF
#!/usr/bin/env bash
# 由 scripts/mini/00_setup_env.sh 自动生成
export MINI_CONDA_ENV=${MINI_CONDA_ENV}
export MINI_DOWNLOAD_DIR=${MINI_DOWNLOAD_DIR}
export MINI_NUSCENES_ROOT=${MINI_NUSCENES_ROOT}
EOF

ln -sfn "${MINI_NUSCENES_ROOT}" "${MINI_REPO_ROOT}/data/nuscenes"

echo "[OK] env.local.sh 已写入"
echo "  MINI_CONDA_ENV=${MINI_CONDA_ENV}"
echo "  MINI_DOWNLOAD_DIR=${MINI_DOWNLOAD_DIR}"
echo "  MINI_NUSCENES_ROOT=${MINI_NUSCENES_ROOT}"
echo "  data/nuscenes -> ${MINI_NUSCENES_ROOT}"
echo ""
echo "后续: conda activate ${MINI_CONDA_ENV}"
echo "      bash scripts/mini/01_download_data.sh"
