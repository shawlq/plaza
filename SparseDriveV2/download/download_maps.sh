#!/usr/bin/env bash
# SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# # shellcheck source=fetch_common.sh
# source "${SCRIPT_DIR}/fetch_common.sh"

# if [[ -d maps ]]; then
#     echo "[跳过] maps 已存在"
#     exit 0
# fi

# fetch_refresh "https://motional-nuplan.s3-ap-northeast-1.amazonaws.com/public/nuplan-v1.1/nuplan-maps-v1.1.zip" "nuplan-maps-v1.1.zip"
unzip nuplan-maps-v1.1.zip
# rm -f nuplan-maps-v1.1.zip
mv nuplan-maps-v1.0 maps
