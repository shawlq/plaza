"""通过 subprocess 调用 git，供 win / linux 入口使用。"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


class GitShuttleError(RuntimeError):
    """Git 命令失败时抛出，附带 stderr。"""

    def __init__(self, message: str, *, stderr: str = "") -> None:
        self.stderr = stderr
        super().__init__(message if not stderr else f"{message}\n{stderr}")


class GitShuttle:
    """在已 clone 的仓库中读写约定载荷文件并 pull/commit/push。"""

    DEFAULT_PAYLOAD_REL = "shuttle_tool/shuttle_payload.txt"

    def __init__(
        self,
        repo_root: str | Path,
        *,
        payload_rel: str | None = None,
        remote: str = "origin",
        branch: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.payload_rel = (payload_rel or self.DEFAULT_PAYLOAD_REL).replace("\\", "/")
        self.remote = remote
        self.branch = branch
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> GitShuttle:
        root = os.environ.get("SHUTTLE_REPO_ROOT", "").strip()
        if not root:
            raise GitShuttleError("未设置环境变量 SHUTTLE_REPO_ROOT（应为已 clone 的仓库根目录绝对路径）")
        payload = os.environ.get("SHUTTLE_PAYLOAD_REL", "").strip() or None
        remote = os.environ.get("SHUTTLE_REMOTE", "origin").strip() or "origin"
        branch = os.environ.get("SHUTTLE_BRANCH", "").strip() or None
        return cls(root, payload_rel=payload, remote=remote, branch=branch)

    def payload_path(self) -> Path:
        return self.repo_root / self.payload_rel

    def _branch_for_ops(self) -> str:
        if self.branch:
            return self.branch
        p = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        name = (p.stdout or "").strip()
        if not name or name == "HEAD":
            raise GitShuttleError("当前不在命名分支上（detached HEAD），请设置 SHUTTLE_BRANCH")
        return name

    def _run_git(
        self,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["git", *args]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise GitShuttleError(f"git 超时（{self.timeout}s）: {' '.join(cmd)}") from e
        except FileNotFoundError as e:
            raise GitShuttleError("未找到 git 可执行文件，请安装 Git 并加入 PATH") from e

        if check and proc.returncode != 0:
            err = (proc.stderr or "").strip()
            out = (proc.stdout or "").strip()
            detail = err or out or "(无输出)"
            raise GitShuttleError(
                f"git 失败（退出码 {proc.returncode}）: {' '.join(cmd)}",
                stderr=detail,
            )
        return proc

    def pull(self) -> None:
        b = self._branch_for_ops()
        self._run_git(["pull", "--rebase", self.remote, b])

    def push(self) -> None:
        b = self._branch_for_ops()
        self._run_git(["push", self.remote, b])

    def _push_with_retry(self) -> None:
        try:
            self.push()
        except GitShuttleError:
            self.pull()
            self.push()

    def send_text(self, text: str) -> None:
        self.pull()
        path = self.payload_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        rel = Path(self.payload_rel).as_posix()
        self._run_git(["add", "--", rel])
        diff = self._run_git(["diff", "--cached", "--quiet"], check=False)
        if diff.returncode == 0:
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        msg = f"shuttle: update {ts}"
        self._run_git(["commit", "-m", msg])
        self._push_with_retry()

    def receive_text(self) -> str:
        self.pull()
        path = self.payload_path()
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")
