#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d trainval_navsim_logs && -d trainval_sensor_blobs/trainval ]]; then
    echo "[跳过] trainval_navsim_logs 与 trainval_sensor_blobs/trainval 已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_trainval.tgz" "openscene_metadata_trainval.tgz"
tar -xzf openscene_metadata_trainval.tgz
rm -f openscene_metadata_trainval.tgz
mv openscene-v1.1/meta_datas trainval_navsim_logs
rm -r openscene-v1.1

mkdir -p trainval_sensor_blobs/trainval
for split in {1..4}; do
    fetch_refresh "https://s3.eu-central-1.amazonaws.com/avg-projects-2/navsim/navtrain_current_${split}.tgz" "navtrain_current_${split}.tgz"
    echo "Extracting file navtrain_current_${split}.tgz"
    tar -xzf "navtrain_current_${split}.tgz"
    rm -f "navtrain_current_${split}.tgz"

    rsync -rv "current_split_${split}/"* trainval_sensor_blobs/trainval
    rm -r "current_split_${split}"
done

for split in {1..4}; do
    fetch_refresh "https://s3.eu-central-1.amazonaws.com/avg-projects-2/navsim/navtrain_history_${split}.tgz" "navtrain_history_${split}.tgz"
    echo "Extracting file navtrain_history_${split}.tgz"
    tar -xzf "navtrain_history_${split}.tgz"
    rm -f "navtrain_history_${split}.tgz"

    rsync -rv "history_split_${split}/"* trainval_sensor_blobs/trainval
    rm -r "history_split_${split}"
done
