"""安装后的 shuttle 命令入口：无参数接收；-h/--help/help 帮助；否则发送。"""

from __future__ import annotations

import sys
from pathlib import Path

from shuttle_tool.common.git_client import GitShuttle, GitShuttleError
from shuttle_tool.common.shuttle_env import linux_env_dir, try_apply_env_dir


def _print_help() -> None:
    sys.stdout.write(
        """用法:
  shuttle                    接收：pull 后把载荷内容打印到标准输出
  shuttle <文本...>          发送：参数以空格连接为正文并提交
  shuttle <文件路径>         发送：若唯一参数为已存在的文件路径，则发送该文件内容
  shuttle -h | --help        显示本帮助
  shuttle help               显示本帮助

环境变量来自 shuttle_tool/linux/.shuttle.env/config（由 install.sh 生成），或由当前 shell export。
未配置时请先运行 shuttle_tool/linux/install.sh。
"""
    )


def _recv() -> int:
    try:
        shuttle = GitShuttle.from_env()
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        print("提示: 请运行 shuttle_tool/linux/install.sh 或配置 linux/.shuttle.env/config。", file=sys.stderr)
        return 1
    try:
        text = shuttle.receive_text()
        sys.stdout.write(text)
        if text and not text.endswith("\n"):
            sys.stdout.write("\n")
        return 0
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        return 2


def _send_body(body: str) -> int:
    try:
        shuttle = GitShuttle.from_env()
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        print("提示: 请运行 shuttle_tool/linux/install.sh 或配置 linux/.shuttle.env/config。", file=sys.stderr)
        return 1
    try:
        shuttle.send_text(body)
        return 0
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        return 2


def _send_path(path: Path) -> int:
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 2
    return _send_body(body)


def main() -> int:
    try_apply_env_dir(linux_env_dir())
    argv = sys.argv[1:]
    if not argv:
        return _recv()
    if argv and argv[0] in ("-h", "--help"):
        _print_help()
        return 0
    if len(argv) == 1 and argv[0] == "help":
        _print_help()
        return 0
    if len(argv) == 1:
        p = Path(argv[0]).expanduser()
        try:
            if p.is_file():
                return _send_path(p)
        except OSError:
            pass
    return _send_body(" ".join(argv))


if __name__ == "__main__":
    raise SystemExit(main())
