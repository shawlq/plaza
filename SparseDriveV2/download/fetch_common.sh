#!/usr/bin/env bash
# 终端颜色（加粗）：成功绿 / 失败红
_FETCH_CLR_OK=$'\033[1;32m'
_FETCH_CLR_ERR=$'\033[1;31m'
_FETCH_CLR_RST=$'\033[0m'

_fetch_echo_done_ok() {
    local out="$1"
    echo "[结束] $out（${_FETCH_CLR_OK}下载成功${_FETCH_CLR_RST}）"
}

_fetch_echo_done_err() {
    local out="$1"
    echo "[结束] $out（${_FETCH_CLR_ERR}下载失败${_FETCH_CLR_RST}）" >&2
}

# 供 download/*.sh source：提供 fetch(url, [outfile])、fetch_resume(url, [outfile])
# fetch：下载前/后打印；本地已存在同名文件则跳过。
# fetch_resume：无本地文件或空文件则全量下载；已有非空文件则尽量用 HEAD 取 Content-Length，
# 若本地已 >= 远端则视为完成（避免对已完整文件仍用 curl -C - 触发 HTTP 416）。
# 可选 DNS：在 source 之前设置 FETCH_NS 或 NS（传给 curl --dns-servers）；不设则用系统解析。

# 返回最终资源的 Content-Length（多段重定向时取最后一行），失败或无则输出空行。
_fetch_content_length() {
    local url="$1"
    local dns="${FETCH_NS:-${NS:-}}"
    local dns_args=()
    [[ -n "$dns" ]] && dns_args=(--dns-servers "$dns")
    curl -sIL --connect-timeout 60 --max-redirs 15 "${dns_args[@]}" "$url" 2>/dev/null \
        | tr -d '\r' \
        | grep -i '^content-length:' \
        | tail -n1 \
        | awk '{print $2}'
}

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

# 断点续传：无文件 / 仅空文件 → 全量下载；非空文件 → 若能取到远端长度则与本地比较，
# 本地已完整则跳过；否则 curl -C -。取不到长度时仍用 -C -，失败后再 HEAD 一次以识别 416「已下完」。
fetch_resume() {
    local url="$1"
    local out="${2:-$(basename "$url")}"
    local dns="${FETCH_NS:-${NS:-}}"
    local dns_args=()
    [[ -n "$dns" ]] && dns_args=(--dns-servers "$dns")

    echo "[开始] $out"

    local local_size=0
    local remote_size=""
    if [[ -f "$out" ]]; then
        local_size=$(stat -c%s "$out" 2>/dev/null || echo 0)
    fi

    local resume_args=()
    if [[ -f "$out" ]]; then
        if [[ "$local_size" -eq 0 ]]; then
            echo "[信息] 本地空文件，删除后全量下载"
            rm -f "$out"
        elif [[ "$local_size" -gt 0 ]]; then
            remote_size=$(_fetch_content_length "$url")
            if [[ -n "$remote_size" ]] && [[ "$remote_size" =~ ^[0-9]+$ ]]; then
                if [[ "$local_size" -gt "$remote_size" ]]; then
                    echo "[警告] 本地 ${local_size} 字节大于远端 ${remote_size}，删除后全量下载"
                    rm -f "$out"
                    local_size=0
                elif [[ "$local_size" -eq "$remote_size" ]]; then
                    echo "[信息] 本地 ${local_size} 字节，远端 Content-Length=${remote_size}，已完整，跳过下载"
                    _fetch_echo_done_ok "$out"
                    return 0
                else
                    echo "[信息] 本地 ${local_size} 字节，远端 ${remote_size}，断点续传（curl -C -）"
                    resume_args=(-C -)
                fi
            else
                echo "[信息] 本地已有 ${local_size} 字节，未取到远端长度，尝试续传（curl -C -）"
                resume_args=(-C -)
            fi
        fi
    else
        echo "[信息] 本地无此文件，全量下载"
    fi

    if curl -fL "${dns_args[@]}" --connect-timeout 60 --retry 3 --retry-delay 2 "${resume_args[@]}" -o "$out" "$url"; then
        _fetch_echo_done_ok "$out"
        return 0
    fi

    # 常见：已完整仍发了 Range → 416；或首次未取到 Content-Length。再 HEAD 比对一次。
    if [[ ${#resume_args[@]} -gt 0 ]]; then
        local_size=$(stat -c%s "$out" 2>/dev/null || echo 0)
        remote_size=$(_fetch_content_length "$url")
        if [[ -n "$remote_size" ]] && [[ "$remote_size" =~ ^[0-9]+$ ]]; then
            if [[ "$local_size" -eq "$remote_size" ]]; then
                echo "[信息] 续传失败（如 HTTP 416）但本地与远端等大（${local_size} 字节），视为已完整"
                _fetch_echo_done_ok "$out"
                return 0
            fi
            if [[ "$local_size" -gt "$remote_size" ]]; then
                echo "[警告] 续传失败后本地 ${local_size} 字节仍大于远端 ${remote_size}，删除后全量重试"
                rm -f "$out"
                if curl -fL "${dns_args[@]}" --connect-timeout 60 --retry 3 --retry-delay 2 -o "$out" "$url"; then
                    _fetch_echo_done_ok "$out"
                    return 0
                fi
            fi
        fi
    fi

    _fetch_echo_done_err "$out"
    return 1
}

# 先删除本地同名文件再下载（解压失败或残留不完整包时避免 fetch 误判已存在而跳过）
fetch_refresh() {
    local url="$1"
    local out="${2:-$(basename "$url")}"
    rm -f "$out"
    fetch "$url" "$out"
}
