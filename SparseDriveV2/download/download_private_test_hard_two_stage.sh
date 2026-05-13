#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d private_test_hard_two_stage && -d private_test_hard_navsim_sensor && -d private_test_hard_navsim_log ]]; then
    echo "[跳过] private_test_hard 数据已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/navsim-v2/navsim_v2.2_private_test_hard_two_stage.tar.gz" "navsim_v2.2_private_test_hard_two_stage.tar.gz"
tar -xzf navsim_v2.2_private_test_hard_two_stage.tar.gz
rm -f navsim_v2.2_private_test_hard_two_stage.tar.gz

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_private_test_hard.tar.gz" "openscene_sensor_private_test_hard.tar.gz"
tar -xzf openscene_sensor_private_test_hard.tar.gz
rm -f openscene_sensor_private_test_hard.tar.gz
mv openscene-v1.1/sensor_blobs/ private_test_hard_navsim_sensor
rm -r openscene-v1.1

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_private_test_hard.tar.gz" "openscene_metadata_private_test_hard.tar.gz"
tar -xzf openscene_metadata_private_test_hard.tar.gz
rm -f openscene_metadata_private_test_hard.tar.gz
mv openscene-v1.1/meta_datas/ private_test_hard_navsim_log
rm -r openscene-v1.1
