#!/usr/bin/env bash
# SparseDrive mini：conda 环境、PyTorch、flash-attn、requirement.txt、deformable_aggregation ops

_sparsedrive_ops_installed() {
    python -c "
import torch
import deformable_aggregation_ext
" >/dev/null 2>&1
}

_prepare_cuda_build_env() {
    python -m pip install -q "ninja>=1.11" 2>/dev/null || true

    if ! command -v nvcc >/dev/null 2>&1 \
        || ! nvcc --version 2>/dev/null | grep -Eq "release 11\.(6|7|8)"; then
        echo "  安装 conda cuda-nvcc 11.8（flash-attn / mmcv 编译需要 ≥11.6）..."
        conda install -y -n "${MINI_CONDA_ENV}" -c nvidia "cuda-nvcc=11.8.89" >/dev/null
        # shellcheck source=/dev/null
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "${MINI_CONDA_ENV}"
    fi

    export CUDA_HOME="${CONDA_PREFIX}"
    export PATH="${CUDA_HOME}/bin:${PATH}"
    export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
}

_write_conda_activate_scripts() {
    local ad="${CONDA_PREFIX}/etc/conda/activate.d"
    local dd="${CONDA_PREFIX}/etc/conda/deactivate.d"
    mkdir -p "${ad}" "${dd}"

    cat > "${ad}/sparsedrive_mini.sh" <<'EOF'
export _SPARSEDRIVE_OLD_CUDA_HOME="${CUDA_HOME-}"
export _SPARSEDRIVE_OLD_LD_LIBRARY_PATH="${LD_LIBRARY_PATH-}"
export CUDA_HOME="${CONDA_PREFIX}"
export PATH="${CONDA_PREFIX}/bin:${PATH}"
export LD_LIBRARY_PATH="${CONDA_PREFIX}/lib:${LD_LIBRARY_PATH:-}"
EOF

    cat > "${dd}/sparsedrive_mini.sh" <<'EOF'
if [ -n "${_SPARSEDRIVE_OLD_CUDA_HOME+x}" ]; then
  export CUDA_HOME="${_SPARSEDRIVE_OLD_CUDA_HOME}"
  unset _SPARSEDRIVE_OLD_CUDA_HOME
fi
if [ -n "${_SPARSEDRIVE_OLD_LD_LIBRARY_PATH+x}" ]; then
  export LD_LIBRARY_PATH="${_SPARSEDRIVE_OLD_LD_LIBRARY_PATH}"
  unset _SPARSEDRIVE_OLD_LD_LIBRARY_PATH
fi
EOF
}

ensure_mini_conda_env() {
    if ! command -v conda >/dev/null 2>&1; then
        echo "错误: 未找到 conda。请先安装 Miniforge/Anaconda。" >&2
        exit 1
    fi
    if conda env list | awk '{print $1}' | grep -Fxq "${MINI_CONDA_ENV}"; then
        echo "[OK] conda 环境已存在: ${MINI_CONDA_ENV}"
        return 0
    fi
    echo "========== 创建 conda 环境: ${MINI_CONDA_ENV} (python=3.8) =========="
    conda create -n "${MINI_CONDA_ENV}" python=3.8 -y
}

install_mini_python_deps() {
    ensure_mini_conda_env
    activate_mini_conda
    _prepare_cuda_build_env
    _write_conda_activate_scripts

    echo "========== 安装 PyTorch (cu116) =========="
    python -m pip install --upgrade pip
    python -m pip install \
        torch==1.13.0+cu116 torchvision==0.14.0+cu116 torchaudio==0.13.0 \
        --extra-index-url https://download.pytorch.org/whl/cu116

    echo "========== 安装 flash-attn =========="
    if ! python -c "import flash_attn" >/dev/null 2>&1; then
        python -m pip install "flash-attn==2.3.2" --no-build-isolation
    else
        echo "[跳过] flash-attn 已安装"
    fi

    echo "========== 安装 requirement.txt =========="
    python -m pip install -r "${MINI_REPO_ROOT}/requirement.txt"

    if ! python -c "import torch; import mmcv; import mmdet" >/dev/null 2>&1; then
        echo "错误: 核心依赖安装后无法 import" >&2
        exit 1
    fi
    echo "[OK] torch $(python -c 'import torch; print(torch.__version__)')"
}

install_sparsedrive_ops() {
    activate_mini_conda
    _prepare_cuda_build_env
    if _sparsedrive_ops_installed; then
        echo "[跳过] deformable_aggregation ops 已安装"
        return 0
    fi
    echo "========== 编译 deformable_aggregation CUDA op =========="
    (
        cd "${MINI_REPO_ROOT}/projects/mmdet3d_plugin/ops"
        rm -rf build *.egg-info 2>/dev/null || true
        python setup.py develop
    )
    if ! _sparsedrive_ops_installed; then
        echo "错误: ops 编译后仍无法 import" >&2
        exit 1
    fi
    echo "[OK] deformable_aggregation ops"
}

install_mini_all_deps() {
    install_mini_python_deps
    install_sparsedrive_ops
}
