#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=fetch_common.sh
source "${SCRIPT_DIR}/fetch_common.sh"

DO_EXTRACT=0
DO_DOWNLOAD=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --extract)
            DO_EXTRACT=1
            DO_DOWNLOAD=0
            ;;
        -h|--help)
            echo "Usage: $(basename "$0") [--extract]"
            echo "  默认仅下载 tgz，不解压；加 --extract 后解压并整理为 mini_navsim_logs / mini_sensor_blobs"
            exit 0
            ;;
        *)
            echo "未知参数: $1（可用 --help 查看用法）" >&2
            exit 1
            ;;
    esac
    shift
done

if [[ -d mini_navsim_logs && -d mini_sensor_blobs ]]; then
    echo "[跳过] mini_navsim_logs 与 mini_sensor_blobs 已存在"
    exit 0
fi

if [[ "$DO_DOWNLOAD" -eq 1 ]]; then

    # 使用 fetch_resume：无文件全量下；有非空文件则 curl -C - 续传（见 fetch_common.sh）
    fetch_resume "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_mini.tgz" "openscene_metadata_mini.tgz"

    for split in {0..31}; do
        fetch_resume "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_camera/openscene_sensor_mini_camera_${split}.tgz" "openscene_sensor_mini_camera_${split}.tgz"
    done

    for split in {0..31}; do
        fetch_resume "https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_lidar/openscene_sensor_mini_lidar_${split}.tgz" "openscene_sensor_mini_lidar_${split}.tgz"
        #tar -xzf "openscene_sensor_mini_lidar_${split}.tgz"
        #rm -f "openscene_sensor_mini_lidar_${split}.tgz"
    done
else
    echo "[跳过下载]"
fi


if [[ "$DO_EXTRACT" -eq 1 ]]; then
    tar -xzf openscene_metadata_mini.tgz
    # rm -f openscene_metadata_mini.tgz
    mv openscene-v1.1/meta_datas mini_navsim_logs
    rm -r openscene-v1.1

    for split in {0..31}; do
        echo "Extracting file openscene_sensor_mini_camera_${split}.tgz"
        tar -xzf "openscene_sensor_mini_camera_${split}.tgz"
        #rm -f "openscene_sensor_mini_camera_${split}.tgz"
    done

    for split in {0..31}; do
        echo "Extracting file openscene_sensor_mini_lidar_${split}.tgz"
        tar -xzf "openscene_sensor_mini_lidar_${split}.tgz"
        #rm -f "openscene_sensor_mini_lidar_${split}.tgz"
    done

    mv openscene-v1.1/sensor_blobs mini_sensor_blobs
    rm -r openscene-v1.1
else
    echo "[跳过解压] 仅下载完成；需要解压时请执行: $(basename "$0") --extract"
fi
