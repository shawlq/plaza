#!/usr/bin/env bash
# 用法:
#   bash scripts/mini/04_eval.sh
#   CHECKPOINT=exp/.../periodic_pdm_ckpts/ep0010.ckpt bash scripts/mini/04_eval.sh
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

if [[ -z "${CHECKPOINT:-}" ]]; then
    CHECKPOINT="$(find "${NAVSIM_EXP_ROOT}/sparsedrive_navmini_train" -path '*/periodic_pdm_ckpts/ep*.ckpt' 2>/dev/null | sort -V | tail -n 1 || true)"
fi
if [[ -z "${CHECKPOINT}" || ! -f "${CHECKPOINT}" ]]; then
    echo "未找到训练 checkpoint，请设置 CHECKPOINT=..." >&2
    exit 1
fi
echo "CHECKPOINT=${CHECKPOINT}"

python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_pdm_score_navtest_v1_fast.py" \
    train_test_split=navmini \
    agent=sparsedrive_agent \
    agent.checkpoint_path="${CHECKPOINT}" \
    experiment_name=sparsedrive_navmini_eval \
    metric_cache_path="${METRIC_CACHE_NAVMINI_V1}" \
    +test_cache_path="${DATA_CACHE_NAVMINI}" \
    dataloader.params.batch_size=8 \
    +agent.config.dataset_version=v1 \
    '+agent.config.metrics=["no_at_fault_collisions","drivable_area_compliance","driving_direction_compliance","time_to_collision_within_bound","comfort","ego_progress"]' \
    '+agent.config.velocity_filter_num=[64,20]'

echo "[OK] 04_eval 完成，结果见 exp/sparsedrive_navmini_eval/*/navtest_v1.csv"
