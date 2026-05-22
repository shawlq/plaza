#!/usr/bin/env bash
# 用法:
#   bash scripts/mini/03_train.sh smoke   # 冒烟（产物带 _smoke 后缀）
#   bash scripts/mini/03_train.sh full    # 完整 mini 训练
#   bash scripts/mini/03_train.sh clear   # 清除 smoke / full 全部训练产物
set -euo pipefail

_MODE="${1:-}"

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_SPARSEDRIVE_ROOT="$(cd "${_SCRIPT_DIR}/../.." && pwd)"

# smoke / full 产物路径（full 保持与原仓库一致的命名）
_ARTIFACT_PATHS=(
    "ckpt/sparsedrive_stage1.pth"
    "ckpt/sparsedrive_stage2.pth"
    "ckpt/sparsedrive_stage1_smoke.pth"
    "ckpt/sparsedrive_stage2_smoke.pth"
    "work_dirs/sparsedrive_small_stage1"
    "work_dirs/sparsedrive_small_stage2"
    "work_dirs/sparsedrive_small_stage1_smoke"
    "work_dirs/sparsedrive_small_stage2_smoke"
    "vis/mini"
)

_clear_artifacts() {
    cd "${_SPARSEDRIVE_ROOT}"
    echo "[clear] 将删除 smoke / full 训练产物（ckpt、work_dirs、vis/mini）"
    local path removed=0
    for path in "${_ARTIFACT_PATHS[@]}"; do
        if [[ -e "${path}" || -L "${path}" ]]; then
            echo "  rm -rf ${path}"
            rm -rf "${path}"
            removed=1
        fi
    done
    if [[ "${removed}" -eq 0 ]]; then
        echo "[clear] 未发现可删除的产物"
    else
        echo "[OK] clear 完成"
    fi
}

if [[ "${_MODE}" == "clear" ]]; then
    _clear_artifacts
    exit 0
fi

if [[ "${_MODE}" != "smoke" && "${_MODE}" != "full" ]]; then
    echo "用法: bash scripts/mini/03_train.sh smoke|full|clear" >&2
    exit 1
fi

# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

_MODE_TAG=""
if [[ "${_MODE}" == "smoke" ]]; then
    _MODE_TAG="_smoke"
fi

STAGE1_CFG="projects/configs/sparsedrive_small_stage1.py"
STAGE2_CFG="projects/configs/sparsedrive_small_stage2.py"
STAGE1_CKPT="ckpt/sparsedrive_stage1${_MODE_TAG}.pth"
STAGE2_CKPT="ckpt/sparsedrive_stage2${_MODE_TAG}.pth"
STAGE1_WORK_DIR="work_dirs/sparsedrive_small_stage1${_MODE_TAG}"
STAGE2_WORK_DIR="work_dirs/sparsedrive_small_stage2${_MODE_TAG}"
STAGE2_LOAD_FROM="ckpt/sparsedrive_stage1${_MODE_TAG}.pth"
GPUS=1

if [[ "${_MODE}" == "smoke" ]]; then
    S1_EPOCHS=2
    S2_EPOCHS=1
else
    S1_EPOCHS=100
    S2_EPOCHS=10
fi

# 与 projects/configs/sparsedrive_small_stage{1,2}.py 中 mini 的 num_iters_per_epoch 一致
_ITERS_PER_EPOCH_S1=$((323 / 8))   # 40
_ITERS_PER_EPOCH_S2=$((323 / 6))   # 53

# IterBasedRunner 只看 runner.max_iters；仅改 num_epochs 不会重算 max_iters。
# --cfg-options 须传多个 key=val 参数，不能用逗号拼接（mmcv DictAction 会把逗号当列表）。
_CFG_OPTS=()
_cfg_options() {
    local epochs="$1"
    local iters_per_epoch="$2"
    local work_dir="$3"
    local max_iters=$((epochs * iters_per_epoch))
    _CFG_OPTS=(
        "num_epochs=${epochs}"
        "runner.max_iters=${max_iters}"
        "work_dir=${work_dir}"
    )
    if [[ "${_MODE}" == "smoke" ]]; then
        local warmup=$((max_iters / 3))
        [[ "${warmup}" -lt 1 ]] && warmup=1
        _CFG_OPTS+=(
            "lr_config.warmup_iters=${warmup}"
            "evaluation.interval=${max_iters}"
            "checkpoint_config.interval=${max_iters}"
        )
    fi
}

_run_stage1() {
    if [[ -f "${STAGE1_CKPT}" && "${_MODE}" == "full" ]]; then
        echo "[skip] 已有 ${STAGE1_CKPT}（删除后重训，或 bash scripts/mini/03_train.sh clear）"
        return 0
    fi
    local max_iters=$((S1_EPOCHS * _ITERS_PER_EPOCH_S1))
    _cfg_options "${S1_EPOCHS}" "${_ITERS_PER_EPOCH_S1}" "${STAGE1_WORK_DIR}"
    echo "[train] stage1 ${_MODE}: ${S1_EPOCHS} epoch(s), ${max_iters} iters"
    echo "[train] work_dir=${STAGE1_WORK_DIR}"
    echo "[train] --cfg-options ${_CFG_OPTS[*]}"
    # 训练期不做 EvalHook（det/tracking/motion/planning）；完整指标用 04_eval.sh
    local -a _train_extra=(--no-validate)
    bash ./tools/dist_train.sh \
        "${STAGE1_CFG}" \
        "${GPUS}" \
        --deterministic \
        "${_train_extra[@]}" \
        --cfg-options "${_CFG_OPTS[@]}"
    mkdir -p ckpt
    cp -L "${STAGE1_WORK_DIR}/latest.pth" "${STAGE1_CKPT}"
    echo "[OK] stage1 -> ${STAGE1_CKPT}"
}

_run_stage2() {
    if [[ ! -f "${STAGE2_LOAD_FROM}" ]]; then
        echo "缺少 stage1 权重 ${STAGE2_LOAD_FROM}，请先完成 stage1" >&2
        exit 1
    fi
    local max_iters=$((S2_EPOCHS * _ITERS_PER_EPOCH_S2))
    _cfg_options "${S2_EPOCHS}" "${_ITERS_PER_EPOCH_S2}" "${STAGE2_WORK_DIR}"
    _CFG_OPTS+=("load_from=${STAGE2_LOAD_FROM}")
    echo "[train] stage2 ${_MODE}: ${S2_EPOCHS} epoch(s), ${max_iters} iters"
    echo "[train] work_dir=${STAGE2_WORK_DIR} load_from=${STAGE2_LOAD_FROM}"
    echo "[train] --cfg-options ${_CFG_OPTS[*]}"
    local -a _train_extra=(--no-validate)
    bash ./tools/dist_train.sh \
        "${STAGE2_CFG}" \
        "${GPUS}" \
        --deterministic \
        "${_train_extra[@]}" \
        --cfg-options "${_CFG_OPTS[@]}"
    mkdir -p ckpt
    cp -L "${STAGE2_WORK_DIR}/latest.pth" "${STAGE2_CKPT}"
    echo "[OK] stage2 -> ${STAGE2_CKPT}"
}

_run_stage1
_run_stage2

echo "[OK] 03_train ${_MODE} 完成"
echo "  stage1: ${STAGE1_WORK_DIR}/"
echo "  stage2: ${STAGE2_WORK_DIR}/"
echo "  ckpt:   ${STAGE2_CKPT}"
