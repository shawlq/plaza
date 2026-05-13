#!/usr/bin/env bash
# 供 download/*.sh source：提供 fetch(url, [outfile])
# 下载前/后打印；本地已存在同名文件则跳过。
# 可选 DNS：在 source 之前设置 FETCH_NS 或 NS（传给 curl --dns-servers）；不设则用系统解析。

fetch() {
    local url="$1"
    local out="${2:-$(basename "$url")}"
    local dns="${FETCH_NS:-${NS:-}}"
    local dns_args=()
    [[ -n "$dns" ]] && dns_args=(--dns-servers "$dns")

    echo "[开始] $out"
    if [[ -f "$out" ]]; then
        echo "[结束] $out（已存在，跳过下载）"
        return 0
    fi
    if curl -fL "${dns_args[@]}" --connect-timeout 60 --retry 3 --retry-delay 2 -o "$out" "$url"; then
        echo "[结束] $out（下载完成）"
    else
        echo "[结束] $out（下载失败）" >&2
        return 1
    fi
}

# 先删除本地同名文件再下载（解压失败或残留不完整包时避免 fetch 误判已存在而跳过）
fetch_refresh() {
    local url="$1"
    local out="${2:-$(basename "$url")}"
    rm -f "$out"
    fetch "$url" "$out"
}
