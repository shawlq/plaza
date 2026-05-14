"""读写 .shuttle.env：在 env_dir/repo 下自动克隆远程仓库，并注入 os.environ。"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_CONFIG_NAME = "config"
REPO_DIR_NAME = "repo"


class ShuttleEnvError(RuntimeError):
    """克隆或更新本地仓库失败。"""


def clone_target(env_dir: Path) -> Path:
    return env_dir / REPO_DIR_NAME


def parse_env_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key:
            out[key] = val
    return out


def load_env_config_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_lines(path.read_text(encoding="utf-8"))


def _is_valid_env_key(key: str) -> bool:
    return bool(key) and key.isascii() and key.replace("_", "").isalnum()


def ensure_repo_cloned(
    env_dir: Path,
    *,
    url: str,
    clone_branch: str | None = None,
    timeout: int = 600,
) -> Path:
    """在 env_dir/repo 克隆或同步 origin URL，返回解析后的仓库根路径。"""
    url = url.strip()
    if not url:
        raise ShuttleEnvError("SHUTTLE_REPO_URL 为空")
    low = url.lower()
    if not (low.startswith("http://") or low.startswith("https://")):
        raise ShuttleEnvError("仅支持以 http:// 或 https:// 开头的远程仓库地址")
    repo = clone_target(env_dir)
    env_dir.mkdir(parents=True, exist_ok=True)

    if (repo / ".git").exists():
        r = subprocess.run(
            ["git", "-C", str(repo), "remote", "set-url", "origin", url],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            raise ShuttleEnvError(f"更新远程地址失败: {err}")
        return repo.resolve()

    if repo.exists():
        raise ShuttleEnvError(f"目录已存在且不是 Git 仓库: {repo}")

    cmd: list[str] = ["git", "clone"]
    if clone_branch:
        cmd.extend(["-b", clone_branch])
    cmd.extend([url, str(repo)])
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as e:
        raise ShuttleEnvError("未找到 git 可执行文件，请安装 Git 并加入 PATH") from e
    except subprocess.TimeoutExpired as e:
        raise ShuttleEnvError(f"git clone 超时（{timeout}s）") from e
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise ShuttleEnvError(f"git clone 失败: {err}")
    return repo.resolve()


def try_apply_env_dir(env_dir: Path) -> None:
    """若未设置 SHUTTLE_REPO_ROOT，则读取 config，按 SHUTTLE_REPO_URL 在 env_dir/repo 克隆并写入环境变量。"""
    if os.environ.get("SHUTTLE_REPO_ROOT", "").strip():
        return
    data = load_env_config_file(env_dir / _CONFIG_NAME)
    url = (data.get("SHUTTLE_REPO_URL") or "").strip()
    clone_branch = (data.get("SHUTTLE_CLONE_BRANCH") or "").strip() or None
    repo_path = clone_target(env_dir)

    if not url:
        return

    ensure_repo_cloned(env_dir, url=url, clone_branch=clone_branch)
    os.environ["SHUTTLE_REPO_ROOT"] = str(repo_path.resolve())
    os.environ["SHUTTLE_REPO_URL"] = url

    for k, v in data.items():
        if not v or not str(v).strip():
            continue
        if k in ("SHUTTLE_REPO_ROOT", "SHUTTLE_REPO_URL"):
            continue
        if _is_valid_env_key(k):
            os.environ[str(k)] = str(v).strip()


def save_env_dir(env_dir: Path, values: dict[str, str], *, header: str) -> None:
    env_dir.mkdir(parents=True, exist_ok=True)
    order = (
        "SHUTTLE_REPO_URL",
        "SHUTTLE_CLONE_BRANCH",
        "SHUTTLE_REPO_ROOT",
        "SHUTTLE_PAYLOAD_REL",
        "SHUTTLE_REMOTE",
        "SHUTTLE_BRANCH",
    )
    lines = [header.rstrip(), ""]
    written: set[str] = set()
    for k in order:
        v = (values.get(k) or "").strip()
        if v:
            lines.append(f"{k}={v}")
            written.add(k)
    for k in sorted(values.keys()):
        if k in written:
            continue
        v = (values.get(k) or "").strip()
        if v and _is_valid_env_key(k):
            lines.append(f"{k}={v}")
    (env_dir / _CONFIG_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def linux_env_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "linux" / ".shuttle.env"


def win_env_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "win" / ".shuttle.env"
