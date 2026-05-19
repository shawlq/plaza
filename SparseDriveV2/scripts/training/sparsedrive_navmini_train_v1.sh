#!/usr/bin/env bash
# Step 4.2: navmini 子集正式训练（50 train / 12 val log，10 epoch）
set -euo pipefail
source "$(dirname "$0")/../mini/env.sh"

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
