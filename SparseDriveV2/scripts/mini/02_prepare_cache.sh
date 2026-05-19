#!/usr/bin/env bash
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=env.sh
source "${_SCRIPT_DIR}/env.sh"

echo "========== dataset cache =========="
python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_dataset_caching.py" \
    agent=sparsedrive_agent \
    experiment_name=cache_navmini \
    train_test_split=navmini \
    force_cache_computation=True \
    cache_path="${DATA_CACHE_NAVMINI}"

echo "========== metric cache (v1) =========="
python "${NAVSIM_DEVKIT_ROOT}/navsim/planning/script/run_metric_caching_v1.py" \
    train_test_split=navmini \
    cache.cache_path="${METRIC_CACHE_NAVMINI_V1}"

echo "[OK] 02_prepare_cache 完成"
