"""Linux 命令行：send / receive。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 支持「python shuttle_tool/linux/cli.py」在未设置 PYTHONPATH 时从仓库根运行
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shuttle_tool.common.git_client import GitShuttle, GitShuttleError


def _read_send_body(args: argparse.Namespace) -> str:
    if args.file:
        p = Path(args.file)
        return p.read_text(encoding="utf-8")
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 Git 仓库收发文本（需配置 SHUTTLE_REPO_ROOT）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_send = sub.add_parser("send", help="pull 后写入载荷并 commit/push")
    p_send.add_argument(
        "--file",
        "-f",
        metavar="PATH",
        help="从该文件读取正文；缺省从标准输入读取",
    )

    sub.add_parser("receive", help="pull 后读取载荷并打印到标准输出")

    args = parser.parse_args()

    try:
        shuttle = GitShuttle.from_env()
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        return 1

    try:
        if args.cmd == "send":
            body = _read_send_body(args)
            shuttle.send_text(body)
            return 0
        if args.cmd == "receive":
            text = shuttle.receive_text()
            sys.stdout.write(text)
            if text and not text.endswith("\n"):
                sys.stdout.write("\n")
            return 0
    except GitShuttleError as e:
        print(str(e), file=sys.stderr)
        return 2
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
