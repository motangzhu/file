@echo off
REM ============================================================
REM  Codex <-> 腾讯云 TI 协议转换代理 启动脚本
REM  用法：双击运行；或放入 shell:startup 实现登录自启
REM  作用：Codex 只认 Responses API，而 TI 的 /v1/responses
REM        不支持 tools；此代理把 Responses 转成 Chat
REM        Completions(非流式) 转发给 TI，再翻回 Responses SSE。
REM ============================================================
if "%TI_API_KEY%"=="" (
  echo [WARN] 环境变量 TI_API_KEY 未设置，代理将因鉴权失败无法工作。
  echo 请先在 系统属性 - 高级 - 环境变量 - 用户变量 中设置 TI_API_KEY=726e8a3060a9ade，再运行本脚本。
  pause
  exit /b 1
)
start "TI-Codex-Proxy" /min "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\Administrator\.codex\ti_responses_proxy.py"
echo [OK] 代理已在后台启动 (监听 127.0.0.1:8787)，可启动/重启 Codex 桌面端。
echo      如需停止：在任务管理器结束 TI-Codex-Proxy 或 python 进程。
