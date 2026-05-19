# SparseDriveV2 — navmini 操作手册

## 0. Conda 环境（一次性）

在 `scripts/mini/config.sh` 中设置 `MINI_CONDA_ENV`（默认 `navsim`；若已有环境如 `sparsev2` 可改为该名称）。

```bash
cd /path/to/SparseDriveV2
# 创建/更新 conda 环境、安装 requirements.txt、编译 sparsedrive ops
bash scripts/mini/00_setup_env.sh
conda activate navsim   # 或你在 config.sh 里写的 MINI_CONDA_ENV
```

## 1. 填写路径

编辑 `scripts/mini/config.sh`：

```bash
MINI_DATA_ROOT="/your/path/SparseDriveV2/data"
MINI_DOWNLOAD_DIR="/your/path/SparseDriveV2/download"
```

## 2. 数据文件与下载链接

### 2.1 OpenScene mini（`01_prepare_data.sh` 自动下载）

| 文件 | URL |
|------|-----|
| `openscene_metadata_mini.tgz` | https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_metadata_mini.tgz |
| `openscene_sensor_mini_camera_0.tgz` … `_31.tgz` | https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_camera/openscene_sensor_mini_camera_{0..31}.tgz |
| `openscene_sensor_mini_lidar_0.tgz` … `_31.tgz` | https://huggingface.co/datasets/OpenDriveLab/OpenScene/resolve/main/openscene-v1.1/openscene_sensor_mini_lidar/openscene_sensor_mini_lidar_{0..31}.tgz |

解压后目录（在 `MINI_DOWNLOAD_DIR`）：

- `mini_navsim_logs/`
- `mini_sensor_blobs/`

### 2.2 nuPlan 地图

| 文件 | URL |
|------|-----|
| `nuplan-maps-v1.1.zip` | https://motional-nuplan.s3-ap-northeast-1.amazonaws.com/public/nuplan-v1.1/nuplan-maps-v1.1.zip |

解压后目录：`${MINI_DATA_ROOT}/maps/`

### 2.3 训练依赖权重

| 保存路径 | URL |
|----------|-----|
| `ckpt/resnet34.bin` | https://huggingface.co/timm/resnet34.a1_in1k/resolve/main/pytorch_model.bin |
| `ckpt/kmeans/path_1024.npy` | https://huggingface.co/wenchaosun/SparseDriveV2/resolve/main/path_1024.npy |
| `ckpt/kmeans/velocity_256.npy` | https://huggingface.co/wenchaosun/SparseDriveV2/resolve/main/velocity_256.npy |
| `ckpt/kmeans/trajectory_1024_256.npz` | https://huggingface.co/wenchaosun/SparseDriveV2/resolve/main/trajectory_1024_256.npz |

### 2.4 软链接目标（`00_setup_env.sh` 自动创建）

| 链接 | 指向 |
|------|------|
| `${MINI_DATA_ROOT}/navsim_logs/mini` | `${MINI_DOWNLOAD_DIR}/mini_navsim_logs` 或其中的 `mini/` 子目录 |
| `${MINI_DATA_ROOT}/sensor_blobs/mini` | `${MINI_DOWNLOAD_DIR}/mini_sensor_blobs` 或其中的 `mini/` 子目录 |

## 3. 执行顺序

```bash
cd /path/to/SparseDriveV2
```

### 3.1 环境变量、Python 依赖与软链接

```bash
bash scripts/mini/00_setup_env.sh
conda activate navsim
```

### 3.2 数据与权重（下载 + 解压；ops 若未装会补装）

```bash
bash scripts/mini/01_prepare_data.sh
```

### 3.3 特征缓存与 metric 缓存

```bash
bash scripts/mini/02_prepare_cache.sh
```

### 3.4 训练

```bash
# 冒烟（2 epoch，4 log）
bash scripts/mini/03_train.sh smoke

# navmini 训练（10 epoch，50/12 log 划分）
bash scripts/mini/03_train.sh full
```

训练 checkpoint：

```text
exp/sparsedrive_navmini_train/<时间戳>/periodic_pdm_ckpts/ep0010.ckpt
```

### 3.5 评测

```bash
# 自动使用最近一次 full 训练的 checkpoint
bash scripts/mini/04_eval.sh
```

或指定权重：

```bash
CHECKPOINT=exp/sparsedrive_navmini_train/<时间戳>/periodic_pdm_ckpts/ep0010.ckpt \
  bash scripts/mini/04_eval.sh
```

评测结果：

```text
exp/sparsedrive_navmini_eval/<时间戳>/navtest_v1.csv
```

## 4. 脚本一览

| 脚本 | 作用 |
|------|------|
| `scripts/mini/config.sh` | 手动填写 `MINI_DATA_ROOT`、`MINI_DOWNLOAD_DIR` |
| `scripts/mini/00_setup_env.sh` | conda 环境、`requirements.txt`、sparsedrive ops、`env.local.sh`、软链接 |
| `scripts/mini/01_prepare_data.sh` | 下载数据/地图/权重（必要时补装 ops） |
| `scripts/mini/02_prepare_cache.sh` | dataset cache + metric cache |
| `scripts/mini/03_train.sh smoke\|full` | 训练 |
| `scripts/mini/04_eval.sh` | PDM 评测 |
