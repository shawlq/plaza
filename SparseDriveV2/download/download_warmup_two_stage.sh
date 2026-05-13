#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d warmup_two_stage ]]; then
    echo "[跳过] warmup_two_stage 已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/navsim-v2/navsim_v2.2_warmup_two_stage.tar.gz" "navsim_v2.2_warmup_two_stage.tar.gz"
tar -xzvf navsim_v2.2_warmup_two_stage.tar.gz
rm -f navsim_v2.2_warmup_two_stage.tar.gz
