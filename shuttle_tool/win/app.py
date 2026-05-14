"""Windows 图形界面：双文本框 + 发送 / 接收。"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

# 支持「在仓库根执行 python shuttle_tool/win/app.py」时能找到 shuttle_tool 包
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import tkinter as tk
from tkinter import messagebox, scrolledtext

from shuttle_tool.common.git_client import GitShuttle, GitShuttleError


def _load_shuttle() -> GitShuttle:
    return GitShuttle.from_env()


def main() -> None:
    if not os.environ.get("SHUTTLE_REPO_ROOT", "").strip():
        root = tk.Tk()
        root.withdraw()
        init_bat = Path(__file__).resolve().parent / "init_env_val.bat"
        messagebox.showerror(
            "配置错误",
            "未设置环境变量 SHUTTLE_REPO_ROOT。\n\n"
            f"请先编辑并运行 init_env_val.bat：\n{init_bat}\n\n"
            "（在该脚本中为 SHUTTLE_REPO_ROOT 赋值后，于同一 CMD 窗口执行该脚本，再启动本程序。）",
        )
        sys.exit(1)
        return

    try:
        shuttle = _load_shuttle()
    except GitShuttleError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("配置错误", str(e))
        sys.exit(1)
        return

    root = tk.Tk()
    root.title("Git 文本穿梭 (shuttle_tool)")
    root.geometry("720x520")

    frm = tk.Frame(root, padx=8, pady=8)
    frm.pack(fill=tk.BOTH, expand=True)

    tk.Label(frm, text="发送（可编辑）").pack(anchor=tk.W)
    send_box = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD)
    send_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

    tk.Label(frm, text="接收（只读）").pack(anchor=tk.W)
    recv_box = scrolledtext.ScrolledText(frm, height=12, wrap=tk.WORD, state=tk.DISABLED)
    recv_box.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

    btn_row = tk.Frame(frm)
    btn_row.pack(fill=tk.X)

    send_btn = tk.Button(btn_row, text="发送", width=12)
    recv_btn = tk.Button(btn_row, text="接收", width=12)
    send_btn.pack(side=tk.LEFT, padx=(0, 8))
    recv_btn.pack(side=tk.LEFT)

    status = tk.StringVar(value=f"仓库: {shuttle.repo_root}")
    tk.Label(frm, textvariable=status, fg="gray").pack(anchor=tk.W, pady=(4, 0))

    def set_recv_text(content: str) -> None:
        recv_box.configure(state=tk.NORMAL)
        recv_box.delete("1.0", tk.END)
        recv_box.insert(tk.END, content)
        recv_box.configure(state=tk.DISABLED)

    def on_send_done(err: BaseException | None) -> None:
        send_btn.configure(state=tk.NORMAL)
        recv_btn.configure(state=tk.NORMAL)
        if err is None:
            status.set("发送完成")
        else:
            status.set("发送失败")
            messagebox.showerror("发送失败", str(err))

    def on_recv_done(err: BaseException | None, text: str | None) -> None:
        send_btn.configure(state=tk.NORMAL)
        recv_btn.configure(state=tk.NORMAL)
        if err is None and text is not None:
            set_recv_text(text)
            status.set("接收完成")
        elif err is not None:
            status.set("接收失败")
            messagebox.showerror("接收失败", str(err))

    def do_send() -> None:
        send_btn.configure(state=tk.DISABLED)
        recv_btn.configure(state=tk.DISABLED)
        status.set("正在发送…")

        def work() -> None:
            err: BaseException | None = None
            try:
                body = send_box.get("1.0", tk.END)
                shuttle.send_text(body)
            except BaseException as e:
                err = e
            root.after(0, lambda: on_send_done(err))

        threading.Thread(target=work, daemon=True).start()

    def do_recv() -> None:
        send_btn.configure(state=tk.DISABLED)
        recv_btn.configure(state=tk.DISABLED)
        status.set("正在接收…")

        def work() -> None:
            err: BaseException | None = None
            text: str | None = None
            try:
                text = shuttle.receive_text()
            except BaseException as e:
                err = e
            root.after(0, lambda: on_recv_done(err, text))

        threading.Thread(target=work, daemon=True).start()

    send_btn.configure(command=do_send)
    recv_btn.configure(command=do_recv)

    root.mainloop()


if __name__ == "__main__":
    main()
