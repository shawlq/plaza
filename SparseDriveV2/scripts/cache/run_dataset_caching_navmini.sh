#!/usr/bin/env bash
# Step 3a: navmini 特征缓存（dataset cache）
set -euo pipefail
source "$(dirname "$0")/../mini/env.sh"

python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_dataset_caching.py" \
    agent=sparsedrive_agent \
    experiment_name=cache_navmini \
    train_test_split=navmini \
    force_cache_computation=True \
    cache_path="${DATA_CACHE_NAVMINI}"
