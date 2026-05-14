"""读写 .shuttle.env 目录下的 config，并注入 os.environ。"""

from __future__ import annotations

import os
from pathlib import Path

_CONFIG_NAME = "config"


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


def try_apply_env_dir(env_dir: Path) -> None:
    """若当前未设置 SHUTTLE_REPO_ROOT，则从 env_dir/config 加载到 os.environ。"""
    if os.environ.get("SHUTTLE_REPO_ROOT", "").strip():
        return
    data = load_env_config_file(env_dir / _CONFIG_NAME)
    for k, v in data.items():
        if v and k.isascii() and k.replace("_", "").isalnum():
            os.environ[str(k)] = str(v)


def save_env_dir(env_dir: Path, values: dict[str, str], *, header: str) -> None:
    env_dir.mkdir(parents=True, exist_ok=True)
    order = (
        "SHUTTLE_REPO_ROOT",
        "SHUTTLE_REPO_URL",
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
        if v and k.isascii() and k.replace("_", "").isalnum():
            lines.append(f"{k}={v}")
    (env_dir / _CONFIG_NAME).write_text("\n".join(lines) + "\n", encoding="utf-8")


def linux_env_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "linux" / ".shuttle.env"


def win_env_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "win" / ".shuttle.env"
