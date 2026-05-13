#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d mini_navsim_logs && -d mini_sensor_blobs ]]; then
    echo "[跳过] mini_navsim_logs 与 mini_sensor_blobs 已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_mini.tgz" "openscene_metadata_mini.tgz"
tar -xzf openscene_metadata_mini.tgz
rm -f openscene_metadata_mini.tgz
mv openscene-v1.1/meta_datas mini_navsim_logs
rm -r openscene-v1.1

for split in {0..31}; do
    fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_camera/openscene_sensor_mini_camera_${split}.tgz" "openscene_sensor_mini_camera_${split}.tgz"
    echo "Extracting file openscene_sensor_mini_camera_${split}.tgz"
    tar -xzf "openscene_sensor_mini_camera_${split}.tgz"
    rm -f "openscene_sensor_mini_camera_${split}.tgz"
done

for split in {0..31}; do
    fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_lidar/openscene_sensor_mini_lidar_${split}.tgz" "openscene_sensor_mini_lidar_${split}.tgz"
    echo "Extracting file openscene_sensor_mini_lidar_${split}.tgz"
    tar -xzf "openscene_sensor_mini_lidar_${split}.tgz"
    rm -f "openscene_sensor_mini_lidar_${split}.tgz"
done

mv openscene-v1.1/sensor_blobs mini_sensor_blobs
rm -r openscene-v1.1
