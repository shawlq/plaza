# Visualization

SparseDriveV2 reuses [NAVSIM visualization](https://github.com/autonomousvision/navsim) (`navsim/visualization/`) and adds a SparseDrive-style CLI for batch rendering and MP4 export.

## Quick start

```bash
# Environment (OPENSCENE_DATA_ROOT, NUPLAN_MAPS_ROOT)
source set_env_val.sh   # or: source scripts/mini/env.sh

# GT + multi-camera + BEV (navmini, 5 scenes)
bash scripts/visualize.sh

# With a trained checkpoint
CHECKPOINT=exp/sparsedrive_navmini_train/.../periodic_pdm_ckpts/ep0010.ckpt \
  MAX_SCENES=3 bash scripts/visualize.sh
```

Outputs:

- `vis/.../combine/*.jpg` — per-frame composites: **cameras | BEV (pred) | BEV (GT)**
- `vis/.../video.mp4` — stitched sequence (same idea as `plaza/SparseDrive` `visualize.sh`)

## Python CLI

```bash
export PYTHONPATH="$(pwd):$PYTHONPATH"

python tools/visualization/visualize.py \
  --split mini \
  --scene-filter navmini \
  --max-scenes 10 \
  --checkpoint path/to/ep0010.ckpt \
  --out-dir vis/demo
```

| Option | Description |
|--------|-------------|
| `--split` | Subfolder under `navsim_logs/` and `sensor_blobs/` (e.g. `mini`, `trainval`) |
| `--scene-filter` | Scene filter YAML name (`navmini`, `navtest`, …) |
| `--checkpoint` | Run SparseDrive inference while visualizing |
| `--predictions-pkl` | Use precomputed `{token: Trajectory}` pickle from eval |
| `--frame-mode` | `current` (default), `history`, or `all` frames per scene |
| `--no-video` | Save JPGs only |
| `--gif` | Extra camera-grid GIF for the first scene |

## Relation to SparseDrive (v1)

| SparseDrive | SparseDriveV2 |
|-------------|----------------|
| `scripts/visualize.sh` | `scripts/visualize.sh` |
| `tools/visualization/visualize.py` | `tools/visualization/visualize.py` |
| MMDet3D config + `results.pkl` | NAVSIM `SceneLoader` + optional checkpoint / predictions pickle |
| nuScenes 6-cam layout | NAVSIM 8-cam 3×3 grid + nuPlan map BEV |

For interactive exploration, see `tutorial/tutorial_visualization.ipynb`.
