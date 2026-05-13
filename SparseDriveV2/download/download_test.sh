#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

if [[ -d test_navsim_logs && -d test_sensor_blobs ]]; then
    echo "[跳过] test_navsim_logs 与 test_sensor_blobs 已存在"
    exit 0
fi

fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_test.tgz" "openscene_metadata_test.tgz"
tar -xzf openscene_metadata_test.tgz
rm -f openscene_metadata_test.tgz

for split in {0..31}; do
    fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_test_camera/openscene_sensor_test_camera_${split}.tgz" "openscene_sensor_test_camera_${split}.tgz"
    echo "Extracting file openscene_sensor_test_camera_${split}.tgz"
    tar -xzf "openscene_sensor_test_camera_${split}.tgz"
    rm -f "openscene_sensor_test_camera_${split}.tgz"
done

for split in {0..31}; do
    fetch_refresh "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_test_lidar/openscene_sensor_test_lidar_${split}.tgz" "openscene_sensor_test_lidar_${split}.tgz"
    echo "Extracting file openscene_sensor_test_lidar_${split}.tgz"
    tar -xzf "openscene_sensor_test_lidar_${split}.tgz"
    rm -f "openscene_sensor_test_lidar_${split}.tgz"
done

mv openscene-v1.1/meta_datas test_navsim_logs
mv openscene-v1.1/sensor_blobs test_sensor_blobs
rm -r openscene-v1.1
