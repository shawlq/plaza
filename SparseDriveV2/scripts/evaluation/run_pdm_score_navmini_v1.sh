#!/usr/bin/env bash
# Step 5: navmini 上 PDM 评测（需先完成 4.2 并指定 CHECKPOINT）
set -euo pipefail
source "$(dirname "$0")/../mini/env.sh"

CHECKPOINT="${CHECKPOINT:-ckpt/sparsedrive_navsimv1.ckpt}"

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
