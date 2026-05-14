@echo off
chcp 65001 >nul
REM 将下面一行中的路径改为本机 Git 仓库 clone 的根目录（绝对路径），保存后在 CMD 中执行本脚本。
REM 设置仅对当前 CMD 窗口生效；若需永久生效，请通过「系统属性 → 高级 → 环境变量」添加 SHUTTLE_REPO_ROOT。

set "SHUTTLE_REPO_ROOT="

REM 填写示例（删除 rem 并改成你的路径，或直接在上一行 set 的引号内填写）：
REM set "SHUTTLE_REPO_ROOT=C:\path\to\your\clone"

if "%SHUTTLE_REPO_ROOT%"=="" (
  echo [错误] 尚未设置 SHUTTLE_REPO_ROOT。请编辑本脚本，在上一行 set 语句中为 SHUTTLE_REPO_ROOT 赋值后重新运行。
  exit /b 1
)

echo 已设置 SHUTTLE_REPO_ROOT=%SHUTTLE_REPO_ROOT%
echo 请在本窗口中启动 shuttle 图形程序，例如: python shuttle_tool\win\app.py
exit /b 0
