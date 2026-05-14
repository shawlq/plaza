# shuttle_tool：通过 Git 仓在 Windows 与 Linux 之间传文本

两台机器处于不同局域网、彼此不可直连，但都能访问同一远程 Git 时，可用本工具把一段文本经仓库同步到另一端。

## 原理

在仓库中约定一个载荷文件（默认 `shuttle_tool/shuttle_payload.txt`）。**发送**会先 `pull --rebase`，写入该文件，`git add` / `commit` / `push`；**接收**会先 `pull`，再读取该文件内容。依赖本机已安装的 `git` 命令，无额外 Python 依赖。

## 环境变量（由工具自动注入）

| 变量 | 说明 |
|------|------|
| `SHUTTLE_REPO_URL` | 远程 HTTP(S) 地址；保存在 `.shuttle.env/config` 中。 |
| `SHUTTLE_REPO_ROOT` | **本地工作区根目录**，固定为 `…/.shuttle.env/repo`（工具自动 `git clone`），勿手填。 |
| `SHUTTLE_CLONE_BRANCH` | 可选，首次 `git clone -b` 使用的分支。 |
| `SHUTTLE_PAYLOAD_REL` | 可选，载荷相对仓库根的路径，默认 `shuttle_tool/shuttle_payload.txt`。 |
| `SHUTTLE_REMOTE` | 可选，默认 `origin`。 |
| `SHUTTLE_BRANCH` | 可选，`pull`/`push` 使用的分支；不设则用当前检出分支。 |

首次克隆完成后，请在目标仓库中配置 `user.name` / `user.email`，并对远程有 **push** 权限。

## 本地目录 `.shuttle.env`（勿提交）

- **Windows**：首次运行 [`shuttle_tool/win/app.py`](shuttle_tool/win/app.py) 时填写 **远程 HTTP(S) 地址**（及可选克隆分支等）；工具将仓库克隆到 **`shuttle_tool/win/.shuttle.env/repo`**，并把配置写入同目录下的 `config`。
- **Linux（install.sh）**：安装脚本同样只询问 **HTTP/HTTPS 远程地址**（不要填本地路径），将仓库克隆到 **`…/shuttle_tool/linux/.shuttle.env/repo`**（在 `PREFIX/lib/shuttle/...` 下），并写入 `linux/.shuttle.env/config`。已安装的 `shuttle` 命令会 `source` 该配置文件。
- **从源码运行 CLI**：若未在 shell 中 `export SHUTTLE_REPO_ROOT`，会读取源码树下的 `shuttle_tool/linux/.shuttle.env/config`；若其中含 `SHUTTLE_REPO_URL` 而本地尚无 `repo/`，会自动克隆。

仓库根 [`.gitignore`](.gitignore) 已忽略 `shuttle_tool/win/.shuttle.env/` 与 `shuttle_tool/linux/.shuttle.env/`。

若已通过环境变量显式设置 `SHUTTLE_REPO_ROOT`，则**不会**再用 `.shuttle.env` 覆盖。

## Windows（图形界面）

在**仓库根目录**执行：

```bat
python shuttle_tool\win\app.py
```

首次运行按弹窗填写远程地址；克隆目录见界面提示（`win\.shuttle.env\repo`）。

## Linux（命令行）

### 安装为系统命令 `shuttle`（推荐）

```bash
bash shuttle_tool/linux/install.sh
```

默认 `PREFIX=/usr/local`；无 root 时可 `PREFIX=$HOME/.local`，并确保 `$HOME/.local/bin` 在 `PATH` 中。安装脚本会 `chown` 配置目录以便当前用户向其中执行 `git clone`。

```text
shuttle                    # 接收
shuttle 要发送的正文        # 发送
shuttle /path/to/file.txt  # 发送文件内容（唯一参数且为已存在文件）
shuttle -h                 # 或 shuttle --help / shuttle help
```

### 不安装、直接用 Python 模块

在仓库根执行；可在 `shuttle_tool/linux/.shuttle.env/config` 中只写 `SHUTTLE_REPO_URL=...`（及可选键），由工具在 `linux/.shuttle.env/repo` 自动克隆。

```bash
python3 -m shuttle_tool.linux.cli send < /tmp/note.txt
python3 -m shuttle_tool.linux.cli receive
```

## 冲突与限制

- 若双方同时发送，可能产生合并冲突，需在本机工作区中手动解决后再操作。
- `push` 失败时会自动再执行一次 `pull --rebase` 后重试 `push`。
- 私仓克隆需本机已配置 Git 凭据（credential helper / SSH 若改用 ssh 地址则不在本工具「仅 HTTP(S)」流程内；当前校验要求 `http(s)://`）。

## 目录说明

- `common/`：`GitShuttle`、`shuttle_env`（`try_apply_env_dir`、`ensure_repo_cloned` 等）。
- `win/`：`app.py`；本地克隆 `win/.shuttle.env/repo/`。
- `linux/`：`cli.py`、`shuttle_cmd.py`、`install.sh`；本地克隆 `linux/.shuttle.env/repo/`。
