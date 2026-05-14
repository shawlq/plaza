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
from shuttle_tool.common.shuttle_env import save_env_dir, try_apply_env_dir, win_env_dir


def _load_shuttle() -> GitShuttle:
    return GitShuttle.from_env()


def _show_first_run_config(env_dir: Path) -> bool:
    root = tk.Tk()
    root.title("首次配置 — Git 文本穿梭")
    root.geometry("560x300")
    root.resizable(True, False)

    var_root = tk.StringVar()
    var_url = tk.StringVar()
    var_payload = tk.StringVar()
    var_remote = tk.StringVar(value="origin")
    var_branch = tk.StringVar()

    frm = tk.Frame(root, padx=10, pady=10)
    frm.pack(fill=tk.BOTH, expand=True)

    row = 0

    def add_row(label: str, var: tk.StringVar) -> None:
        nonlocal row
        tk.Label(frm, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        tk.Entry(frm, textvariable=var, width=58).grid(row=row, column=1, sticky=tk.EW, pady=4)
        row += 1

    add_row("本地仓库根目录（必填）", var_root)
    add_row("远程 HTTP(S) 地址（可选）", var_url)
    add_row("载荷相对路径（可选）", var_payload)
    add_row("远程名（可选）", var_remote)
    add_row("分支名（可选）", var_branch)
    frm.grid_columnconfigure(1, weight=1)

    ok_flag = False

    def on_ok() -> None:
        nonlocal ok_flag
        raw = var_root.get().strip()
        if not raw:
            messagebox.showerror("配置", "请填写本地仓库根目录。")
            return
        try:
            p = Path(raw).expanduser().resolve()
        except OSError:
            messagebox.showerror("配置", "路径无效。")
            return
        if not p.is_dir():
            messagebox.showerror("配置", "该路径不是文件夹。")
            return
        if not (p / ".git").exists():
            if not messagebox.askyesno("配置", "该路径下未发现 .git，是否仍要继续？"):
                return
        data: dict[str, str] = {"SHUTTLE_REPO_ROOT": str(p)}
        u = var_url.get().strip()
        if u:
            data["SHUTTLE_REPO_URL"] = u
        pl = var_payload.get().strip()
        if pl:
            data["SHUTTLE_PAYLOAD_REL"] = pl
        rem = var_remote.get().strip()
        if rem:
            data["SHUTTLE_REMOTE"] = rem
        br = var_branch.get().strip()
        if br:
            data["SHUTTLE_BRANCH"] = br
        save_env_dir(
            env_dir,
            data,
            header="# shuttle_tool Windows 本地配置 — 勿提交到 Git 仓库",
        )
        for k, v in data.items():
            os.environ[k] = v
        ok_flag = True
        root.destroy()

    def on_cancel() -> None:
        root.destroy()

    btns = tk.Frame(frm)
    btns.grid(row=row, column=0, columnspan=2, pady=(14, 0))
    tk.Button(btns, text="确定", command=on_ok, width=10).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="取消", command=on_cancel, width=10).pack(side=tk.LEFT, padx=6)

    root.mainloop()
    return ok_flag


def _ensure_win_config(env_dir: Path) -> bool:
    try_apply_env_dir(env_dir)
    if os.environ.get("SHUTTLE_REPO_ROOT", "").strip():
        return True
    return _show_first_run_config(env_dir)


def main() -> None:
    env_dir = win_env_dir()
    if not _ensure_win_config(env_dir):
        sys.exit(1)

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
