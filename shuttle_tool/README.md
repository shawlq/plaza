# shuttle_tool：通过 Git 仓在 Windows 与 Linux 之间传文本

两台机器处于不同局域网、彼此不可直连，但都能访问同一远程 Git 时，可用本工具把一段文本经仓库同步到另一端。

## 原理

在仓库中约定一个载荷文件（默认 `shuttle_tool/shuttle_payload.txt`）。**发送**会先 `pull --rebase`，写入该文件，`git add` / `commit` / `push`；**接收**会先 `pull`，再读取该文件内容。依赖标准 `git` 命令，无额外 Python 依赖。

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SHUTTLE_REPO_ROOT` | 是 | 本机已 clone 的**该仓库根目录**绝对路径（与远程通信的 working copy）。 |
| `SHUTTLE_PAYLOAD_REL` | 否 | 载荷相对仓库根的路径，默认 `shuttle_tool/shuttle_payload.txt`。 |
| `SHUTTLE_REMOTE` | 否 | 远程名，默认 `origin`。 |
| `SHUTTLE_BRANCH` | 否 | 与远程同步的分支名；不设则使用当前检出分支（`git rev-parse --abbrev-ref HEAD`）。 |

使用前请在目标克隆中配置 `user.name` / `user.email`，并对远程有 **push** 权限。

## Windows（图形界面）

在**仓库根目录**（含 `shuttle_tool` 包的那一层）打开终端，设置 `SHUTTLE_REPO_ROOT` 指向本机 clone 根路径（通常就是当前仓库根），然后：

```bat
set SHUTTLE_REPO_ROOT=C:\path\to\your\clone
python shuttle_tool\win\app.py
```

界面：上方为可编辑发送区，下方为只读接收区；按钮「发送」「接收」对应 `send_text` / `receive_text`。长时间 Git 操作在后台线程执行，避免界面卡死。

## Linux（命令行）

同样在仓库根执行（或确保 `PYTHONPATH` 含仓库根）：

```bash
export SHUTTLE_REPO_ROOT=/path/to/your/clone
# 若系统仅有 python3 无 python，请将下文命令中的 python 换为 python3
# 发送：从标准输入
echo 'hello' | python -m shuttle_tool.linux.cli send
# 发送：从文件
python -m shuttle_tool.linux.cli send --file /tmp/note.txt
# 接收：打印到标准输出
python -m shuttle_tool.linux.cli receive
```

也可直接运行脚本（脚本内会尝试把仓库根加入 `sys.path`）：

```bash
python shuttle_tool/linux/cli.py send < /tmp/note.txt
python shuttle_tool/linux/cli.py receive
```

## 冲突与限制

- 若双方同时发送，可能产生合并冲突，需在本机仓库中手动解决后再用工具或命令行完成推送。
- `push` 失败时会自动再执行一次 `pull --rebase` 后重试 `push`；仍失败请根据终端 / 弹窗中的 git 输出排查。
- 本工具不负责 `git clone`，仅操作已有工作区。

## 目录说明

- `common/`：`GitShuttle`（`pull` / `send_text` / `receive_text`），供 Win / Linux 调用。
- `win/`：Tkinter 图形入口 `app.py`。
- `linux/`：命令行入口 `cli.py`。
