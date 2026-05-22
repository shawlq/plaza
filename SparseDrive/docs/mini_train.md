# SparseDrive — nuScenes mini 操作手册

在单卡 GPU 上完成 **mini 数据准备 → 训练（stage1+2）→ 评测 → 可视化**。  
脚本位于 `scripts/mini/`，结构参考 SparseDriveV2 的 `docs/mini_train.md`。

## 0. 前置条件

- Linux + NVIDIA GPU（建议 ≥24GB 显存）
- [Conda](https://docs.conda.io/)（Miniforge/Anaconda 均可）
- [AWS CLI](https://aws.amazon.com/cli/)（`aws s3 cp --no-sign-request` 下载 nuScenes）
- 磁盘：mini 归档约 **8GB**，解压后约 **15GB**

## 1. 填写路径

编辑 `scripts/mini/config.sh`：

```bash
MINI_DOWNLOAD_DIR="/your/path/sparsedrive/archives"   # .tgz / .zip 下载目录
MINI_NUSCENES_ROOT="/your/path/sparsedrive/nuscenes" # 解压后的 nuscenes 根
MINI_CONDA_ENV="sparsedrive"                          # conda 环境名
```

## 2. mini 所需数据文件

`01_download_data.sh` 仅从 Motional 公开桶拉取以下文件（**不含** trainval 分卷）：

| 文件 | 说明 |
|------|------|
| `can_bus.zip` | CAN bus 扩展 |
| `md5.checksum` | 校验（可选核对） |
| `nuScenes-map-expansion-v1.3.zip` | 地图扩展（`create_data` 需要） |
| `v1.0-mini.tgz` | mini 样本与标注 |
| `v1.0-test_blobs*.tgz`、`v1.0-test_meta.tgz` | 官方 test 集（mini 流程仅下载存档；训练/评测用 mini val） |

来源：`s3://motional-nuscenes/public/v1.0/`（`aws s3 cp --no-sign-request --region ap-northeast-1`）。

`02_prepare_data.sh` 会解压 **can_bus、v1.0-mini、地图** 到 `MINI_NUSCENES_ROOT`，并软链为仓库内 `data/nuscenes`。

## 3. 执行顺序

在仓库根目录执行（将 `/path/to/SparseDrive` 换成你的路径）：

```bash
cd /path/to/SparseDrive
```

### 3.1 环境与依赖（一次性）

创建 conda 环境、安装 PyTorch cu116、`flash-attn`、mmcv/mmdet、编译 `deformable_aggregation` ops，并写入 `scripts/mini/env.local.sh`。

```bash
bash scripts/mini/00_setup_env.sh
conda activate sparsedrive   # 或 config.sh 中的 MINI_CONDA_ENV
```

**flash-attn / nvcc：** 若 `pip install` 报 CUDA 版本不足，在已激活环境中执行（详见实验笔记）：

```bash
conda install -y 'cuda-nvcc=11.8.89' -c nvidia
export CUDA_HOME="$CONDA_PREFIX"
export PATH="$CONDA_PREFIX/bin:$PATH"
pip install 'flash-attn==2.3.2' --no-build-isolation
```

`00_setup_env.sh` 会在 conda 的 `activate.d` 中写入 `CUDA_HOME` 与 `LD_LIBRARY_PATH`（缓解 `CXXABI_1.3.15` 等问题）。

### 3.2 下载数据

```bash
bash scripts/mini/01_download_data.sh
```

### 3.3 解压、生成 infos、kmeans、预训练权重

```bash
bash scripts/mini/02_prepare_data.sh
```

产出：

- `data/infos/mini/nuscenes_infos_{train,val}.pkl`
- `data/kmeans/kmeans_*.npy`
- `ckpt/resnet50-19c8e357.pth`

### 3.4 训练

默认 **单卡**（`num_gpus=1`），配置中 `version='mini'`。训练使用 **IterBasedRunner**，总步数由 `runner.max_iters` 决定；`03_train.sh` 会按 epoch 数同步设置 `num_epochs` 与 `runner.max_iters`（以及 smoke 下的 warmup / eval / checkpoint 间隔）。

mini 训练集约 **323** 条样本，每 epoch 迭代数（与 `sparsedrive_small_stage{1,2}.py` 一致）：

| 阶段 | batch | iters/epoch | smoke | full |
|------|-------|-------------|-------|------|
| stage1 | 8 | 40 | 2 epoch → **80** iters | 100 epoch → **4000** iters |
| stage2 | 6 | 53 | 1 epoch → **53** iters | 10 epoch → **530** iters |

日志中应看到 `Iter [k/N]` 的 **N** 与上表一致（例如 smoke stage1 为 `.../80`），而不是默认配置里的 4000。

```bash
# 冒烟：stage1 80 iters + stage2 53 iters（验证流程，约百步级；训练期不做 val）
bash scripts/mini/03_train.sh smoke

# 完整 mini：stage1 4000 + stage2 530 iters（耗时较长）
bash scripts/mini/03_train.sh full

# 清除 smoke / full 全部训练产物（ckpt、work_dirs、vis/mini）
bash scripts/mini/03_train.sh clear
```

smoke 与 full **产物路径分离**，避免互相覆盖：

| 模式 | stage1 ckpt | stage2 ckpt | work_dirs |
|------|-------------|-------------|-----------|
| smoke | `ckpt/sparsedrive_stage1_smoke.pth` | `ckpt/sparsedrive_stage2_smoke.pth` | `work_dirs/sparsedrive_small_stage{1,2}_smoke/` |
| full | `ckpt/sparsedrive_stage1.pth` | `ckpt/sparsedrive_stage2.pth` | `work_dirs/sparsedrive_small_stage{1,2}/` |

`03_train.sh`（smoke / full）均使用 `--no-validate`，训练结束不跑 EvalHook（det / tracking / motion / planning）。末轮 motion 在 `motion_threshhold=0.2` 下若预测过少会触发 nuScenes `Invalid box type: None`。**指标请用** `04_eval.sh`。

Checkpoint（**full**；smoke 见上表 `_smoke` 后缀）：

```text
ckpt/sparsedrive_stage1.pth
ckpt/sparsedrive_stage2.pth
work_dirs/sparsedrive_small_stage{1,2}/
```

### 3.5 评测

```bash
bash scripts/mini/04_eval.sh
```

或指定权重：

```bash
CHECKPOINT=ckpt/sparsedrive_stage2.pth bash scripts/mini/04_eval.sh
```

预测结果：`work_dirs/sparsedrive_small_stage2/results.pkl`

### 3.6 可视化

```bash
bash scripts/mini/05_visualize.sh
```

输出：`vis/mini/`（含 `combine/` 下合成视频）。

## 4. 脚本一览

| 脚本 | 作用 |
|------|------|
| `scripts/mini/config.sh` | 路径与 conda 环境名 |
| `scripts/mini/00_setup_env.sh` | 环境、依赖、ops、`data/nuscenes` 软链 |
| `scripts/mini/01_download_data.sh` | 下载 mini 所需 nuScenes 归档 |
| `scripts/mini/02_prepare_data.sh` | 解压、infos、kmeans、ResNet50 |
| `scripts/mini/03_train.sh smoke\|full\|clear` | stage1 + stage2 训练；`clear` 清除全部训练产物 |
| `scripts/mini/04_eval.sh` | 评测并写出 `results.pkl` |
| `scripts/mini/05_visualize.sh` | BEV/相机可视化 |

各脚本会 `source scripts/mini/env.sh`（自动 `conda activate` 与 `PYTHONPATH`）。

## 5. 与全量 trainval 的差异

| 项目 | mini | trainval |
|------|------|----------|
| 数据脚本 | `scripts/mini/01_download_data.sh` | 需自行下载 trainval 分卷 |
| 配置 `version` | `mini` | `trainval` |
| infos 目录 | `data/infos/mini/` | `data/infos/` |
| GPU | 1（已调 batch/lr） | 原论文 8 卡 |

全量流程见 [quick_start.md](quick_start.md)。

## 6. 常见问题

1. **`create_data` / map 报错** — 确认已解压 `nuScenes-map-expansion-v1.3.zip` 到 `data/nuscenes/maps/`（含 `expansion` 等目录）。
2. **kmeans `need at least one array`** — mini 上 `kmeans_plan.py` 已对空 command 打桩；确保 `02` 已生成 `data/infos/mini/*.pkl` 并完成软链。
3. **stage2 找不到 stage1 权重** — `03_train.sh` 会将 `work_dirs/.../latest.pth` 复制到对应模式的 `ckpt/sparsedrive_stage1[_smoke].pth`；smoke 与 full 路径不同，互不覆盖。
4. **full 误用 smoke 的 stage1** — 若曾用旧脚本混跑，执行 `bash scripts/mini/03_train.sh clear` 后重跑 `full`。
5. **多进程抢单卡** — 保持 `tools/dist_*.sh` 中 `GPUS=1`；勿在未改配置时提高 `num_gpus`。
6. **smoke 仍显示 `/4000`** — 先看开训日志是否打印 `--cfg-options num_epochs=2 runner.max_iters=80 ...`（**参数之间是空格，不能逗号拼接**）。若 `work_dirs/..._smoke/` 里 `runner.max_iters` 仍为 4000，即 cfg 未生效；可 `03_train.sh clear` 后重跑 smoke。
7. **`Invalid box type: None`（tracking / motion）** — nuScenes 在**预测框为 0** 时会报错（tracking 用 `tracking_threshold=0.2` 过滤 `cls_scores`；motion 用 `motion_threshhold=0.2`）。常见原因：未在 mini 上训练、仍用 `02_prepare_data` 下载的预训练 `ckpt/*.pth`（此时 det mAP 也会极低）。`04_eval.sh` 已对空 tracking/motion 自动跳过并打印提示；请先 `03_train.sh` 再用 `work_dirs/.../epoch_*.pth` 评测。训练阶段 `03_train.sh` 已默认 `--no-validate`。
