#!/usr/bin/env bash
# Step 3b: navmini PDM metric cache（训练 metric loss 必需）
set -euo pipefail
source "$(dirname "$0")/../mini/env.sh"

python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_metric_caching_v1.py" \
    train_test_split=navmini \
    cache.cache_path="${METRIC_CACHE_NAVMINI_V1}"
