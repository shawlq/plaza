#!/usr/bin/env bash
# 安装 shuttle 到 PREFIX：按 HTTP(S) 克隆到 linux/.shuttle.env/repo，并写入 config。
# 非 root 默认 PREFIX=$HOME/.local，并可将 bin 追加到 PATH（~/.bashrc）。
# 用法: bash install.sh | bash install.sh --prefix DIR | bash install.sh --uninstall [--prefix DIR]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHUTTLE_TOOL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DO_UNINSTALL=0
SHOW_HELP=0
CLI_PREFIX=""
NO_PATH_SNIPPET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uninstall) DO_UNINSTALL=1; shift ;;
    --prefix)
      [[ $# -ge 2 ]] || { echo "缺少 --prefix 参数值" >&2; exit 1; }
      CLI_PREFIX="$2"
      shift 2
      ;;
    --no-path-snippet) NO_PATH_SNIPPET=1; shift ;;
    -h|--help) SHOW_HELP=1; shift ;;
    *)
      echo "未知参数: $1（可用 --help）" >&2
      exit 1
      ;;
  esac
done

_expand_tilde() {
  local p="$1"
  if [[ "${p}" == "~" ]]; then
    echo "${HOME}"
  elif [[ "${p}" == ~/* ]]; then
    echo "${HOME}${p#~}"
  else
    echo "${p}"
  fi
}

# 安装记录与 PATH 片段所针对的「真实用户」主目录（sudo 安装时用 SUDO_USER）
_target_home() {
  if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    getent passwd "${SUDO_USER}" | cut -d: -f6
  else
    echo "${HOME}"
  fi
}

_manifest_path() {
  local th
  th="$(_target_home)"
  echo "${th}/.local/share/shuttle/install.paths"
}

_show_help() {
  cat <<'EOF'
shuttle_tool Linux 安装脚本

安装:
  bash shuttle_tool/linux/install.sh
  sudo env PREFIX=/usr/local bash shuttle_tool/linux/install.sh
  bash shuttle_tool/linux/install.sh --prefix ~/.local

  未指定 PREFIX 时：非 root 默认 $HOME/.local；root 默认 /usr/local。
  安装到 /usr、/opt 下且非 root 时会使用 sudo。
  默认把安装目录下的 bin 追加到「真实用户」的 ~/.bashrc 的 PATH（新终端生效）；
  可用 --no-path-snippet 跳过；若当前 PATH 已包含该 bin 则不会重复写入。

卸载:
  bash shuttle_tool/linux/install.sh --uninstall
  bash shuttle_tool/linux/install.sh --uninstall --prefix ~/.local

  根据 ~/.local/share/shuttle/install.paths 执行 rm -rf <prefix>/lib/shuttle、
  rm -f <prefix>/bin/shuttle，并尽量移除上述 PATH 片段。
  若无记录文件，可用 --prefix 指明安装前缀（默认尝试 $HOME/.local）。
EOF
}

if [[ "${SHOW_HELP}" -eq 1 ]]; then
  _show_help
  exit 0
fi

_remove_path_snippet() {
  local rc="$1"
  [[ -f "${rc}" ]] || return 0
  if grep -q '# shuttle_tool PATH begin' "${rc}" 2>/dev/null; then
    sed -i '/# shuttle_tool PATH begin/,/# shuttle_tool PATH end/d' "${rc}"
  fi
}

_append_path_snippet() {
  local rc="$1" bindir="$2"
  mkdir -p "$(dirname "${rc}")"
  [[ -f "${rc}" ]] || touch "${rc}"
  if grep -q '# shuttle_tool PATH begin' "${rc}" 2>/dev/null; then
    return 0
  fi
  {
    echo ""
    echo "# shuttle_tool PATH begin"
    echo "export PATH=\"${bindir}:\$PATH\""
    echo "# shuttle_tool PATH end"
  } >>"${rc}"
}

_do_uninstall() {
  local manifest th prefix libdir bindir rc had_manifest path_snippet
  th="$(_target_home)"
  manifest="$(_manifest_path)"
  rc="${th}/.bashrc"
  had_manifest=0
  path_snippet=0
  prefix=""
  libdir=""
  bindir=""

  if [[ -n "${CLI_PREFIX}" ]]; then
    prefix="$(_expand_tilde "${CLI_PREFIX}")"
    libdir="${prefix}/lib/shuttle"
    bindir="${prefix}/bin"
  elif [[ -f "${manifest}" ]]; then
    had_manifest=1
    # shellcheck disable=SC1090
    source "${manifest}"
    prefix="${INST_PREFIX:-}"
    libdir="${INST_LIBDIR:-}"
    bindir="${INST_BINDIR:-}"
    rc="${INST_BASHRC:-${rc}}"
    path_snippet="${INST_PATH_SNIPPET:-0}"
  else
    prefix="$(_expand_tilde "${PREFIX:-"${HOME}/.local"}")"
    libdir="${prefix}/lib/shuttle"
    bindir="${prefix}/bin"
  fi

  if [[ -z "${libdir}" || -z "${bindir}" ]]; then
    libdir="${prefix}/lib/shuttle"
    bindir="${prefix}/bin"
  fi

  echo "=== shuttle 卸载 ==="
  echo "执行: rm -rf ${libdir}"
  echo "执行: rm -f ${bindir}/shuttle"
  rm -rf "${libdir}"
  rm -f "${bindir}/shuttle"

  if [[ "${had_manifest}" -eq 1 && "${path_snippet}" == "1" ]]; then
    _remove_path_snippet "${rc}"
    echo "已从 ${rc} 移除 PATH 片段（若存在）。"
  elif [[ "${had_manifest}" -eq 0 ]]; then
    _remove_path_snippet "${rc}"
  fi

  if [[ "${had_manifest}" -eq 1 ]]; then
    rm -f "${manifest}"
    rmdir "$(dirname "${manifest}")" 2>/dev/null || true
    rmdir "$(dirname "$(dirname "${manifest}")")" 2>/dev/null || true
  fi

  echo "卸载完成。"
}

if [[ "${DO_UNINSTALL}" -eq 1 ]]; then
  _do_uninstall
  exit 0
fi

# ---------- 安装 ----------
if [[ -n "${CLI_PREFIX}" ]]; then
  PREFIX="$(_expand_tilde "${CLI_PREFIX}")"
elif [[ -n "${PREFIX:-}" ]]; then
  PREFIX="$(_expand_tilde "${PREFIX}")"
else
  if [[ "$(id -u)" -eq 0 ]]; then
    PREFIX="/usr/local"
  else
    PREFIX="${HOME}/.local"
  fi
fi

LIBDIR="${PREFIX}/lib/shuttle"
BINDIR="${PREFIX}/bin"
CONFIG_DIR="${LIBDIR}/shuttle_tool/linux/.shuttle.env"
CONFIG_PATH="${CONFIG_DIR}/config"
CLONE_DIR="${CONFIG_DIR}/repo"

maybe_sudo=()
if [[ "$(id -u)" != "0" ]]; then
  case "${PREFIX}" in
    /usr/*|/opt/*)
      if command -v sudo >/dev/null 2>&1; then
        maybe_sudo=(sudo)
      else
        echo "安装到 ${PREFIX} 需要 sudo，或使用无需 root 的前缀，例如:" >&2
        echo "  bash $0 --prefix \"\$HOME/.local\"" >&2
        exit 1
      fi
      ;;
  esac
fi

_chown_for_clone() {
  local d="$1"
  if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    local g
    g="$(id -gn "${SUDO_USER}" 2>/dev/null || echo "${SUDO_USER}")"
    chown -R "${SUDO_USER}:${g}" "${d}"
  else
    chown -R "$(id -un):$(id -gn)" "${d}" 2>/dev/null || true
  fi
}

_run_git_as_clone_user() {
  if [[ "$(id -u)" -eq 0 && -n "${SUDO_USER:-}" ]]; then
    local uh
    uh="$(getent passwd "${SUDO_USER}" | cut -d: -f6)"
    sudo -u "${SUDO_USER}" -H env HOME="${uh}" "$@"
  else
    "$@"
  fi
}

echo "=== shuttle 安装：PREFIX=${PREFIX} ==="
echo "  克隆目录: ${CLONE_DIR}"
echo "  配置文件: ${CONFIG_PATH}"
echo ""
read -r -p "Git 仓库 HTTP/HTTPS 地址（必填，例如 https://github.com/org/repo.git；不要填本地路径）: " URL || true
URL="${URL//\"/}"
URL="${URL//\'/}"
URL="${URL#"${URL%%[![:space:]]*}"}"
URL="${URL%"${URL##*[![:space:]]}"}"
if [[ -z "${URL}" ]]; then
  echo "未填写仓库地址，已中止。" >&2
  exit 1
fi
if [[ ! "${URL}" =~ ^https?:// ]]; then
  echo "地址必须以 http:// 或 https:// 开头（不要填本地路径）。" >&2
  exit 1
fi

read -r -p "克隆分支（可选，回车使用远程默认分支）: " CLONE_BRANCH || true
CLONE_BRANCH="${CLONE_BRANCH//\"/}"
CLONE_BRANCH="${CLONE_BRANCH#"${CLONE_BRANCH%%[![:space:]]*}"}"
CLONE_BRANCH="${CLONE_BRANCH%"${CLONE_BRANCH##*[![:space:]]}"}"

read -r -p "SHUTTLE_PAYLOAD_REL（可选，回车使用程序默认）: " PAYLOAD || true
PAYLOAD="${PAYLOAD//\"/}"
PAYLOAD="${PAYLOAD#"${PAYLOAD%%[![:space:]]*}"}"
PAYLOAD="${PAYLOAD%"${PAYLOAD##*[![:space:]]}"}"

read -r -p "SHUTTLE_REMOTE（可选，回车使用 origin）: " REMOTE || true
REMOTE="${REMOTE//\"/}"
REMOTE="${REMOTE#"${REMOTE%%[![:space:]]*}"}"
REMOTE="${REMOTE%"${REMOTE##*[![:space:]]}"}"

read -r -p "SHUTTLE_BRANCH（可选，回车表示使用当前检出分支）: " BRANCH || true
BRANCH="${BRANCH//\"/}"
BRANCH="${BRANCH#"${BRANCH%%[![:space:]]*}"}"
BRANCH="${BRANCH%"${BRANCH##*[![:space:]]}"}"

"${maybe_sudo[@]}" mkdir -p "${LIBDIR}" "${BINDIR}"
"${maybe_sudo[@]}" rm -rf "${LIBDIR}/shuttle_tool"
"${maybe_sudo[@]}" cp -a "${SHUTTLE_TOOL_DIR}" "${LIBDIR}/shuttle_tool"
"${maybe_sudo[@]}" rm -rf "${CONFIG_DIR}"
"${maybe_sudo[@]}" mkdir -p "${CONFIG_DIR}"
_chown_for_clone "${CONFIG_DIR}"

if [[ -e "${CLONE_DIR}" ]] && [[ ! -d "${CLONE_DIR}/.git" ]]; then
  echo "目标目录已存在且不是 Git 仓库: ${CLONE_DIR}" >&2
  exit 1
fi

if [[ -d "${CLONE_DIR}/.git" ]]; then
  echo "已存在本地克隆，更新 remote 并 pull: ${CLONE_DIR}"
  _run_git_as_clone_user git -C "${CLONE_DIR}" remote set-url origin "${URL}"
  _run_git_as_clone_user git -C "${CLONE_DIR}" pull --rebase || true
else
  echo "正在克隆到: ${CLONE_DIR}"
  if [[ -n "${CLONE_BRANCH}" ]]; then
    _run_git_as_clone_user git clone -b "${CLONE_BRANCH}" "${URL}" "${CLONE_DIR}"
  else
    _run_git_as_clone_user git clone "${URL}" "${CLONE_DIR}"
  fi
fi
_chown_for_clone "${CONFIG_DIR}"

tmp_cfg="$(mktemp)"
{
  echo "# Generated by shuttle_tool/linux/install.sh — 勿提交到 Git 仓库"
  printf 'SHUTTLE_REPO_URL=%q\n' "${URL}"
  if [[ -n "${CLONE_BRANCH}" ]]; then
    printf 'SHUTTLE_CLONE_BRANCH=%q\n' "${CLONE_BRANCH}"
  fi
  printf 'SHUTTLE_REPO_ROOT=%q\n' "${CLONE_DIR}"
  if [[ -n "${PAYLOAD}" ]]; then
    printf 'SHUTTLE_PAYLOAD_REL=%q\n' "${PAYLOAD}"
  fi
  if [[ -n "${REMOTE}" ]]; then
    printf 'SHUTTLE_REMOTE=%q\n' "${REMOTE}"
  fi
  if [[ -n "${BRANCH}" ]]; then
    printf 'SHUTTLE_BRANCH=%q\n' "${BRANCH}"
  fi
} >"${tmp_cfg}"
"${maybe_sudo[@]}" cp "${tmp_cfg}" "${CONFIG_PATH}"
rm -f "${tmp_cfg}"

"${maybe_sudo[@]}" tee "${BINDIR}/shuttle" >/dev/null <<EOF
#!/usr/bin/env bash
set -e
CONFIG="${CONFIG_PATH}"
if [[ ! -f "\$CONFIG" ]]; then
  echo "缺少配置文件: ${CONFIG_PATH}，请重新运行 shuttle_tool/linux/install.sh。" >&2
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "\$CONFIG"
set +a
export PYTHONPATH="${LIBDIR}\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m shuttle_tool.linux.shuttle_cmd "\$@"
EOF
"${maybe_sudo[@]}" chmod +x "${BINDIR}/shuttle"

th="$(_target_home)"
manifest="$(_manifest_path)"
mkdir -p "$(dirname "${manifest}")"
PATH_SNIPPET=0
bashrc="${th}/.bashrc"
if [[ "${NO_PATH_SNIPPET}" -eq 0 ]]; then
  case ":${PATH}:" in
    *":${BINDIR}:"*) ;;
    *)
      _append_path_snippet "${bashrc}" "${BINDIR}"
      PATH_SNIPPET=1
      echo "已将 ${BINDIR} 追加到 ${bashrc} 的 PATH（重新打开终端或 source ~/.bashrc 后生效）。"
      ;;
  esac
fi

{
  echo "INST_PREFIX=${PREFIX}"
  echo "INST_LIBDIR=${LIBDIR}"
  echo "INST_BINDIR=${BINDIR}"
  echo "INST_BASHRC=${bashrc}"
  echo "INST_PATH_SNIPPET=${PATH_SNIPPET}"
} >"${manifest}"

echo ""
echo "已安装:"
echo "  启动脚本: ${BINDIR}/shuttle"
echo "  程序库:   ${LIBDIR}/shuttle_tool"
echo "  本地克隆: ${CLONE_DIR}"
echo "  配置文件: ${CONFIG_PATH}"
echo "  卸载记录: ${manifest}"
echo ""
echo "用法: shuttle -h"
