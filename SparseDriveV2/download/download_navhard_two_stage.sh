#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d navhard_two_stage ]]; then
    echo "[跳过] navhard_two_stage 已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/navsim-v2/navsim_v2.2_navhard_two_stage_curr_sensors.tar.gz" "navsim_v2.2_navhard_two_stage_curr_sensors.tar.gz"
fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/navsim-v2/navsim_v2.2_navhard_two_stage_hist_sensors.tar.gz" "navsim_v2.2_navhard_two_stage_hist_sensors.tar.gz"
fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/navsim-v2/navsim_v2.2_navhard_two_stage_scene_pickles.tar.gz" "navsim_v2.2_navhard_two_stage_scene_pickles.tar.gz"
tar -xzvf navsim_v2.2_navhard_two_stage_curr_sensors.tar.gz
tar -xzvf navsim_v2.2_navhard_two_stage_hist_sensors.tar.gz
tar -xzvf navsim_v2.2_navhard_two_stage_scene_pickles.tar.gz
rm -f navsim_v2.2_navhard_two_stage_curr_sensors.tar.gz
rm -f navsim_v2.2_navhard_two_stage_hist_sensors.tar.gz
rm -f navsim_v2.2_navhard_two_stage_scene_pickles.tar.gz
