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

在**仓库根目录**（含 `shuttle_tool` 包的那一层）打开 CMD。推荐先编辑并运行 [`shuttle_tool/win/init_env_val.bat`](shuttle_tool/win/init_env_val.bat)：在其中的 `set "SHUTTLE_REPO_ROOT=..."` 填写本机 Git clone 根目录后执行，以设置当前窗口的 `SHUTTLE_REPO_ROOT`（仅对本 CMD 窗口生效）。若未设置该变量就启动程序，会提示你执行上述脚本。

也可手动：

```bat
set SHUTTLE_REPO_ROOT=C:\path\to\your\clone
python shuttle_tool\win\app.py
```

界面：上方为可编辑发送区，下方为只读接收区；按钮「发送」「接收」对应 `send_text` / `receive_text`。长时间 Git 操作在后台线程执行，避免界面卡死。

## Linux（命令行）

### 安装为系统命令 `shuttle`（推荐）

在仓库中执行（默认安装到 `/usr/local`；无 root 时可使用 `PREFIX=$HOME/.local`，并确保 `$HOME/.local/bin` 在 `PATH` 中）：

```bash
bash shuttle_tool/linux/install.sh
```

安装脚本会交互询问 `SHUTTLE_REPO_ROOT` 等变量，并写入 **`$HOME/.shuttle.info`**（本地配置，**勿提交**；仓库根 [`.gitignore`](.gitignore) 已忽略 `.shuttle.info` 以防误放在仓库内）。

安装后的用法：

```text
shuttle                    # 接收：pull 后打印载荷
shuttle 要发送的正文        # 发送：多词会以空格连接
shuttle /path/to/file.txt  # 发送：唯一参数为已存在文件路径时，发送文件内容
shuttle -h                 # 或 shuttle --help / shuttle help：帮助
```

### 不安装、直接用 Python 模块

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
- `win/`：Tkinter 图形入口 `app.py`；`init_env_val.bat` 用于在本机 CMD 中设置 `SHUTTLE_REPO_ROOT`。
- `linux/`：`cli.py`（`send` / `receive` 子命令）、`shuttle_cmd.py`（安装后的 `shuttle` 入口）、`install.sh`（安装脚本）。
