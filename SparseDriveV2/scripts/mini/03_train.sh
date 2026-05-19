#!/usr/bin/env bash
# 用法: bash scripts/mini/03_train.sh smoke
#       bash scripts/mini/03_train.sh full
set -euo pipefail

_MODE="${1:-}"
if [[ "${_MODE}" != "smoke" && "${_MODE}" != "full" ]]; then
    echo "用法: bash scripts/mini/03_train.sh smoke|full" >&2
    exit 1
fi

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

if [[ "${_MODE}" == "smoke" ]]; then
    python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_training.py" \
        --config-name tiny_training \
        agent=sparsedrive_agent \
        experiment_name=sparsedrive_navmini_smoke \
        train_test_split=navmini \
        use_cache_without_dataset=True \
        force_cache_computation=False \
        cache_path="${DATA_CACHE_NAVMINI}" \
        dataloader.params.batch_size=4 \
        dataloader.params.num_workers=4 \
        trainer.params.max_epochs=2 \
        agent.lr=0.0001 \
        +agent.config.dataset_version=v1 \
        '+agent.config.metrics=["no_at_fault_collisions","drivable_area_compliance","driving_direction_compliance","time_to_collision_within_bound","comfort","ego_progress"]' \
        '+agent.config.velocity_filter_num=[64,20]'
else
    python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_training.py" \
        --config-name navmini_training \
        agent=sparsedrive_agent \
        experiment_name=sparsedrive_navmini_train \
        train_test_split=navmini \
        use_cache_without_dataset=True \
        force_cache_computation=False \
        cache_path="${DATA_CACHE_NAVMINI}" \
        dataloader.params.batch_size=8 \
        dataloader.params.num_workers=8 \
        trainer.params.max_epochs=10 \
        agent.lr=0.0001 \
        +agent.config.dataset_version=v1 \
        '+agent.config.metrics=["no_at_fault_collisions","drivable_area_compliance","driving_direction_compliance","time_to_collision_within_bound","comfort","ego_progress"]' \
        '+agent.config.velocity_filter_num=[64,20]'
fi

echo "[OK] 03_train ${_MODE} 完成"
