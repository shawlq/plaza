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
import tkinter.font as tkfont
from tkinter import messagebox, scrolledtext

from shuttle_tool.common.git_client import GitShuttle, GitShuttleError
from shuttle_tool.common.shuttle_env import ShuttleEnvError, save_env_dir, try_apply_env_dir, win_env_dir

_GEOM_FILE = "window_geometry.txt"


def _load_saved_geometry(env_dir: Path) -> str | None:
    path = env_dir / _GEOM_FILE
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return None


def _save_window_geometry(env_dir: Path, root: tk.Tk) -> None:
    try:
        root.update_idletasks()
        geom = root.winfo_geometry()
        if not geom:
            return
        env_dir.mkdir(parents=True, exist_ok=True)
        (env_dir / _GEOM_FILE).write_text(
            "# shuttle_tool 主窗口 geometry（勿提交到 Git）\n" + geom + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _apply_smaller_fonts(_root: tk.Tk) -> None:
    """略缩小默认与等宽字体（正号 point 尺寸）。"""
    try:
        for name in ("TkDefaultFont", "TkTextFont", "TkFixedFont"):
            f = tkfont.nametofont(name)
            sz = f.cget("size")
            if isinstance(sz, int) and sz > 0:
                f.configure(size=max(8, sz - 2))
    except (tk.TclError, OSError, ValueError):
        pass


def _load_shuttle() -> GitShuttle:
    return GitShuttle.from_env()


def _is_http_url(s: str) -> bool:
    t = s.strip().lower()
    return t.startswith("http://") or t.startswith("https://")


def _show_first_run_config(env_dir: Path) -> bool:
    root = tk.Tk()
    root.title("首次配置 — Git 文本穿梭")
    root.geometry("580x320")
    root.resizable(True, False)

    var_url = tk.StringVar()
    var_clone_branch = tk.StringVar()
    var_payload = tk.StringVar()
    var_remote = tk.StringVar(value="origin")
    var_branch = tk.StringVar()

    frm = tk.Frame(root, padx=10, pady=10)
    frm.pack(fill=tk.BOTH, expand=True)

    row = 0

    def add_row(label: str, var: tk.StringVar) -> None:
        nonlocal row
        tk.Label(frm, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        tk.Entry(frm, textvariable=var, width=60).grid(row=row, column=1, sticky=tk.EW, pady=4)
        row += 1

    add_row("远程仓库 HTTP(S) 地址（必填）", var_url)
    add_row("克隆分支（可选，回车默认远程默认分支）", var_clone_branch)
    add_row("载荷相对路径（可选）", var_payload)
    add_row("远程名（可选）", var_remote)
    add_row("同步分支（可选，pull/push）", var_branch)
    frm.grid_columnconfigure(1, weight=1)

    tk.Label(
        frm,
        text=f"仓库将克隆到: {env_dir / 'repo'}",
        fg="gray",
        font=("TkDefaultFont", 8),
    ).grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 6))
    row += 1

    ok_flag = False

    def on_ok() -> None:
        nonlocal ok_flag
        url = var_url.get().strip()
        if not url:
            messagebox.showerror("配置", "请填写远程仓库 HTTP(S) 地址。")
            return
        if not _is_http_url(url):
            messagebox.showerror("配置", "地址必须以 http:// 或 https:// 开头。")
            return

        data: dict[str, str] = {"SHUTTLE_REPO_URL": url}
        cb = var_clone_branch.get().strip()
        if cb:
            data["SHUTTLE_CLONE_BRANCH"] = cb
        pl = var_payload.get().strip()
        if pl:
            data["SHUTTLE_PAYLOAD_REL"] = pl
        rem = var_remote.get().strip()
        if rem:
            data["SHUTTLE_REMOTE"] = rem
        br = var_branch.get().strip()
        if br:
            data["SHUTTLE_BRANCH"] = br

        lbl = tk.Label(frm, text="正在克隆仓库，请稍候…", fg="blue")
        lbl.grid(row=row, column=0, columnspan=2, pady=6)
        root.update_idletasks()
        try:
            save_env_dir(
                env_dir,
                data,
                header="# shuttle_tool Windows 本地配置 — 勿提交到 Git 仓库",
            )
            try_apply_env_dir(env_dir)
        except ShuttleEnvError as e:
            messagebox.showerror("克隆失败", str(e))
            return
        finally:
            try:
                lbl.destroy()
            except tk.TclError:
                pass

        if not os.environ.get("SHUTTLE_REPO_ROOT", "").strip():
            messagebox.showerror("配置", "克隆完成后仍未设置 SHUTTLE_REPO_ROOT。")
            return

        data["SHUTTLE_REPO_ROOT"] = os.environ["SHUTTLE_REPO_ROOT"]
        save_env_dir(
            env_dir,
            data,
            header="# shuttle_tool Windows 本地配置 — 勿提交到 Git 仓库",
        )
        ok_flag = True
        root.destroy()

    def on_cancel() -> None:
        root.destroy()

    btns = tk.Frame(frm)
    btns.grid(row=row + 1, column=0, columnspan=2, pady=(10, 0))
    tk.Button(btns, text="确定", command=on_ok, width=10).pack(side=tk.LEFT, padx=6)
    tk.Button(btns, text="取消", command=on_cancel, width=10).pack(side=tk.LEFT, padx=6)

    root.mainloop()
    return ok_flag


def _ensure_win_config(env_dir: Path) -> bool:
    try:
        try_apply_env_dir(env_dir)
    except ShuttleEnvError as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("配置", str(e))
        root.destroy()
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
    _apply_smaller_fonts(root)
    saved = _load_saved_geometry(env_dir)
    root.geometry(saved if saved else "720x520")

    frm = tk.Frame(root, padx=6, pady=6)
    frm.pack(fill=tk.BOTH, expand=True)

    btn_row = tk.Frame(frm)
    btn_row.pack(fill=tk.X, pady=(0, 6))

    send_btn = tk.Button(btn_row, text="发送", width=10)
    recv_btn = tk.Button(btn_row, text="接收", width=10)
    send_btn.pack(side=tk.LEFT, padx=(0, 8))
    recv_btn.pack(side=tk.LEFT)

    status = tk.StringVar(value=f"仓库: {shuttle.repo_root}")
    tk.Label(frm, textvariable=status, fg="gray").pack(anchor=tk.W, pady=(0, 6))

    tk.Label(frm, text="发送（可编辑）").pack(anchor=tk.W)
    send_box = scrolledtext.ScrolledText(frm, height=11, wrap=tk.WORD)
    send_box.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

    tk.Label(frm, text="接收（只读）").pack(anchor=tk.W)
    recv_box = scrolledtext.ScrolledText(frm, height=11, wrap=tk.WORD, state=tk.DISABLED)
    recv_box.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

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

    def _on_close() -> None:
        _save_window_geometry(env_dir, root)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    root.mainloop()


if __name__ == "__main__":
    main()
