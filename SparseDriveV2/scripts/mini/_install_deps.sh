#!/usr/bin/env bash
# 安装 mini 锁定依赖与 sparsedrive CUDA ops（需已设置 MINI_REPO_ROOT、MINI_CONDA_ENV）

_MINI_LOCK="${MINI_REPO_ROOT}/scripts/mini/requirements-mini.lock.txt"
_NUPLAN_GIT="nuplan-devkit @ git+https://github.com/motional/nuplan-devkit/@nuplan-devkit-v1.2"

_sparsedrive_ops_installed() {
    # 扩展依赖 libtorch，须先 import torch 再加载 .so
    python -c "
import torch
import deformable_aggregation_ext
import deformable_aggregation_with_depth_ext
" >/dev/null 2>&1
}

_prepare_cuda_build_env() {
    # PyTorch 2.0.1 为 CUDA 11.7 构建；系统 /usr/bin/nvcc 11.5 + GCC 11 会导致扩展编译失败
    python -m pip install -q "ninja>=1.11"

    if ! command -v nvcc >/dev/null 2>&1 \
        || ! nvcc --version 2>/dev/null | grep -q "release 11.7"; then
        echo "  安装 conda cuda-nvcc 11.7（与 torch 2.0.1 对齐）..."
        conda install -y -n "${MINI_CONDA_ENV}" -c nvidia cuda-nvcc=11.7.99 >/dev/null
        # shellcheck source=/dev/null
        source "$(conda info --base)/etc/profile.d/conda.sh"
        conda activate "${MINI_CONDA_ENV}"
    fi

    export CUDA_HOME="${CONDA_PREFIX}"
    export PATH="${CUDA_HOME}/bin:${PATH}"
    export FORCE_CUDA=1

    # CUDA 11.x 在 Ubuntu 上应使用 g++-10 作为 host compiler，避免 std::function 编译错误
    if command -v g++-10 >/dev/null 2>&1; then
        export CC=/usr/bin/gcc-10
        export CXX=/usr/bin/g++-10
        export CUDAHOSTCXX=/usr/bin/g++-10
    fi

    if [[ -z "${TORCH_CUDA_ARCH_LIST:-}" ]]; then
        export TORCH_CUDA_ARCH_LIST
        TORCH_CUDA_ARCH_LIST=$(python -c "
import re
import subprocess
import torch

def nvcc_minor():
    try:
        out = subprocess.check_output(['nvcc', '--version'], text=True)
        m = re.search(r'release (\d+)\.(\d+)', out)
        return (int(m.group(1)), int(m.group(2))) if m else (11, 7)
    except Exception:
        return (11, 7)

if not torch.cuda.is_available():
    print('8.6+PTX')
else:
    major, minor = torch.cuda.get_device_capability(0)
    arch = f'{major}.{minor}'
    nv_maj, nv_min = nvcc_minor()
    # sm_89 (Ada) 需 CUDA >= 11.8；11.7 nvcc 用 8.6+PTX 前向兼容
    if major > 8 or (major == 8 and minor >= 9):
        if (nv_maj, nv_min) < (11, 8):
            print('8.6+PTX')
        else:
            print(arch)
    else:
        print(arch)
" 2>/dev/null || echo "8.6+PTX")
    fi
    echo "  CUDA: $(nvcc --version | sed -n 's/.*release \([0-9.]*\).*/\1/p' | head -1)  CUDAHOSTCXX=${CUDAHOSTCXX:-默认}  ARCH=${TORCH_CUDA_ARCH_LIST}"
}

_ensure_python_ok() {
    local major minor
    major=$(python -c 'import sys; print(sys.version_info.major)')
    minor=$(python -c 'import sys; print(sys.version_info.minor)')
    if [[ "${major}" -ne 3 ]] || [[ "${minor}" -lt 9 ]] || [[ "${minor}" -gt 11 ]]; then
        echo "错误: 需要 Python 3.9–3.11，当前为 ${major}.${minor}" >&2
        echo "  建议: conda env create -n ${MINI_CONDA_ENV} -f ${MINI_REPO_ROOT}/environment.yml" >&2
        exit 1
    fi
    if [[ "${minor}" -ne 9 ]]; then
        echo "[提示] 官方推荐 Python 3.9 (environment.yml)；当前 ${major}.${minor}，guppy3 等依赖已按版本自动 pin"
    fi
}

ensure_mini_conda_env() {
    local env_name="${MINI_CONDA_ENV:-navsim}"
    if ! command -v conda >/dev/null 2>&1; then
        echo "错误: 未找到 conda。请先安装 Miniforge/Anaconda。" >&2
        exit 1
    fi
    if conda env list | awk '{print $1}' | grep -Fxq "${env_name}"; then
        echo "[OK] conda 环境已存在: ${env_name}"
        return 0
    fi
    echo "========== 创建 conda 环境: ${env_name} (python=3.9) =========="
    conda env create -n "${env_name}" -f "${MINI_REPO_ROOT}/environment.yml"
}

install_mini_python_deps() {
    ensure_mini_conda_env
    activate_mini_conda
    _ensure_python_ok

    if [[ ! -f "${_MINI_LOCK}" ]]; then
        echo "错误: 缺少锁定依赖文件 ${_MINI_LOCK}" >&2
        exit 1
    fi

    echo "========== 安装 Python 依赖 (requirements-mini.lock.txt) =========="
    # 固定 pip 版本，避免与 setuptools 65.5.1 / torch 2.0.1 组合时出现解析异常
    python -m pip install "pip==24.3.1" "wheel>=0.38"

    echo "  [1/4] 核心数值栈 (numpy / scipy / pandas) ..."
    python -m pip install \
        "setuptools==65.5.1" \
        "numpy==1.23.5" \
        "scipy==1.11.4" \
        "pandas==2.0.3" \
        "pillow==10.4.0" \
        "matplotlib==3.7.5"

    echo "  [2/4] PyTorch 与训练框架 ..."
    python -m pip install \
        "torch==2.0.1" \
        "torchvision==0.15.2" \
        "pytorch-lightning==2.2.1" \
        "tensorboard==2.16.2" \
        "protobuf==3.20.3"

    echo "  [3/4] 其余锁定依赖 ..."
    python -m pip install -r "${_MINI_LOCK}"

    echo "  [4/4] nuplan-devkit (git) ..."
    python -m pip install "${_NUPLAN_GIT}"

    if ! python -c "import torch" >/dev/null 2>&1; then
        echo "错误: torch 安装后仍无法 import，请检查 pip 输出" >&2
        exit 1
    fi
    if ! python -c "import nuplan" >/dev/null 2>&1; then
        echo "错误: nuplan-devkit 安装后仍无法 import nuplan" >&2
        exit 1
    fi
    echo "[OK] torch $(python -c 'import torch; print(torch.__version__)')"
    echo "[OK] numpy $(python -c 'import numpy; print(numpy.__version__)')"
}

install_navsim_package() {
    activate_mini_conda
    echo "========== 安装 navsim 包 (editable) =========="
    # 脚本以绝对路径调用时 sys.path 不含仓库根目录，须 pip -e 或 PYTHONPATH
    python -m pip install -q -e "${MINI_REPO_ROOT}" --no-build-isolation --no-deps
    if ! python -c "import navsim" >/dev/null 2>&1; then
        echo "错误: navsim 安装后仍无法 import" >&2
        exit 1
    fi
    echo "[OK] navsim $(python -c 'import navsim; print(navsim.__file__)')"
}

install_sparsedrive_ops() {
    activate_mini_conda
    if _sparsedrive_ops_installed; then
        echo "[跳过] sparsedrive ops 已安装"
        return 0
    fi
    echo "========== 编译安装 sparsedrive ops =========="
    _prepare_cuda_build_env
    local ops_dir="${MINI_REPO_ROOT}/navsim/agents/sparsedrive/ops"
    (
        cd "${ops_dir}"
        rm -rf build *.egg-info
        python -m pip install -e . --no-build-isolation
    )
    if ! _sparsedrive_ops_installed; then
        echo "错误: sparsedrive ops 编译后仍无法 import（需 deformable_aggregation_ext 与 deformable_aggregation_with_depth_ext）" >&2
        exit 1
    fi
    echo "[OK] sparsedrive ops"
}

install_mini_all_deps() {
    install_mini_python_deps
    install_navsim_package
    install_sparsedrive_ops
}
