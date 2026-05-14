# shuttle_tool：通过 Git 仓在 Windows 与 Linux 之间传文本

两台机器处于不同局域网、彼此不可直连，但都能访问同一远程 Git 时，可用本工具把一段文本经仓库同步到另一端。

## 原理

在仓库中约定一个载荷文件（默认 `shuttle_tool/shuttle_payload.txt`）。**发送**会先 `pull --rebase`，写入该文件，`git add` / `commit` / `push`；**接收**会先 `pull`，再读取该文件内容。依赖标准 `git` 命令，无额外 Python 依赖。

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `SHUTTLE_REPO_ROOT` | 是 | 本机已 clone 的**工作区根目录**（实际执行 `git pull` / `push` 的路径）。 |
| `SHUTTLE_REPO_URL` | 否 | 远程 HTTP(S) 地址，仅作记录；Linux `install.sh` 会写入。 |
| `SHUTTLE_PAYLOAD_REL` | 否 | 载荷相对仓库根的路径，默认 `shuttle_tool/shuttle_payload.txt`。 |
| `SHUTTLE_REMOTE` | 否 | 远程名，默认 `origin`。 |
| `SHUTTLE_BRANCH` | 否 | 与远程同步的分支名；不设则使用当前检出分支。 |

使用前请在目标克隆中配置 `user.name` / `user.email`，并对远程有 **push** 权限。

## 本地配置目录 `.shuttle.env`（勿提交）

- **Windows**：首次运行 [`shuttle_tool/win/app.py`](shuttle_tool/win/app.py) 时会弹出对话框，填写**本地 Git 仓库根目录**等信息；保存到 **`shuttle_tool/win/.shuttle.env/config`**。之后启动会自动加载。
- **Linux**：由 [`shuttle_tool/linux/install.sh`](shuttle_tool/linux/install.sh) 根据你输入的 **HTTP/HTTPS 远程地址**（不要填本地路径）执行 `git clone` 到 `$HOME/.shuttle/repos/<仓库名>`，并把 `SHUTTLE_REPO_ROOT` 等写入**已安装程序树内的** `.../shuttle_tool/linux/.shuttle.env/config`。从源码直接跑 `cli.py` / `shuttle_cmd.py` 时，则会读取源码树下的 `shuttle_tool/linux/.shuttle.env/config`（若存在）。

仓库根 [`.gitignore`](.gitignore) 已忽略 `shuttle_tool/win/.shuttle.env/` 与 `shuttle_tool/linux/.shuttle.env/`，请勿将其中内容提交到 Git。

若已通过系统或 shell 设置了 `SHUTTLE_REPO_ROOT`，则**不会**再用 `.shuttle.env` 覆盖。

## Windows（图形界面）

在**仓库根目录**打开 CMD 或 PowerShell，执行：

```bat
python shuttle_tool\win\app.py
```

首次运行按弹窗填写**本地 clone 根目录**（必填）及可选字段；配置保存在 `win/.shuttle.env/` 下。

## Linux（命令行）

### 安装为系统命令 `shuttle`（推荐）

在仓库中执行（默认 `PREFIX=/usr/local`；无 root 时可使用 `PREFIX=$HOME/.local`，并确保 `$HOME/.local/bin` 在 `PATH` 中）：

```bash
bash shuttle_tool/linux/install.sh
```

安装脚本会要求填写 **Git 仓库的 HTTP/HTTPS 地址**（例如 `https://github.com/org/repo.git`，**不要填本地路径**），在本机用户目录下克隆到 `$HOME/.shuttle/repos/...`，并把 `SHUTTLE_REPO_ROOT` 指向该克隆；可选询问载荷路径、远程名、分支名。配置文件位于安装前缀内的 `lib/shuttle/shuttle_tool/linux/.shuttle.env/config`。

安装后的用法：

```text
shuttle                    # 接收
shuttle 要发送的正文        # 发送（多词会以空格连接）
shuttle /path/to/file.txt  # 发送：唯一参数为已存在文件时读文件内容
shuttle -h                 # 或 shuttle --help / shuttle help：帮助
```

### 不安装、直接用 Python 模块

在仓库根执行（或设置 `PYTHONPATH`）。可先手动创建 `shuttle_tool/linux/.shuttle.env/config`，格式为每行 `KEY=value`，与上述变量一致。

```bash
export SHUTTLE_REPO_ROOT=/path/to/your/clone
echo 'hello' | python3 -m shuttle_tool.linux.cli send
python3 -m shuttle_tool.linux.cli send --file /tmp/note.txt
python3 -m shuttle_tool.linux.cli receive
```

也可：

```bash
python3 shuttle_tool/linux/cli.py send < /tmp/note.txt
python3 shuttle_tool/linux/cli.py receive
```

## 冲突与限制

- 若双方同时发送，可能产生合并冲突，需在本机仓库中手动解决后再用工具或命令行完成推送。
- `push` 失败时会自动再执行一次 `pull --rebase` 后重试 `push`；仍失败请根据终端 / 弹窗中的 git 输出排查。
- 本工具不负责首次 `git clone`（Windows 侧需用户自行 clone 并填写本地路径；Linux `install.sh` 会代为 clone 远程 HTTP(S) 仓库）。

## 目录说明

- `common/`：`GitShuttle`、`shuttle_env`（读写 `.shuttle.env/config`）。
- `win/`：Tkinter 入口 `app.py`；首次运行写 `win/.shuttle.env/`。
- `linux/`：`cli.py`、`shuttle_cmd.py`、`install.sh`；配置目录 `linux/.shuttle.env/`（由安装脚本或手动维护）。
