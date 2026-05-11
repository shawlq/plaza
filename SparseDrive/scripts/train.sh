#!/usr/bin/env bash
# Run from SparseDrive repo root. Single GPU: GPUS=1 via tools/dist_train.sh --nproc_per_node.

set -euo pipefail

STAGE1_CKPT="ckpt/sparsedrive_stage1.pth"

if [[ -f "$STAGE1_CKPT" ]]; then
  echo "Found $STAGE1_CKPT — skipping stage1, running stage2 only."
else
  ## stage1
  bash ./tools/dist_train.sh \
     projects/configs/sparsedrive_small_stage1.py \
     1 \
     --deterministic

  # Stage2's load_from is ckpt/sparsedrive_stage1.pth, but MMDet only writes under work_dirs/.
  # Copy the latest stage1 weights to the fixed path stage2 expects (-L resolves latest.pth symlink).
  mkdir -p ckpt
  cp -L work_dirs/sparsedrive_small_stage1/latest.pth "$STAGE1_CKPT"
fi

## stage2
bash ./tools/dist_train.sh \
   projects/configs/sparsedrive_small_stage2.py \
   1 \
   --deterministic
