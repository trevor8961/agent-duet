#!/usr/bin/env bash
# agent-duet 一键停止：停前端、停后端。幂等。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN_DIR="$ROOT/.run"

info() { printf '\033[1;34m[agent-duet]\033[0m %s\n' "$1"; }

# 按 PID 文件停（更精准）
for name in frontend backend; do
  pidfile="$RUN_DIR/${name}.pid"
  if [ -f "$pidfile" ]; then
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      info "已停止 ${name}（pid ${pid}）"
    fi
    rm -f "$pidfile"
  fi
done

# 兜底：按进程名停（覆盖手动启动、无 pid 文件的情况）
pkill -f "uvicorn app.main:app" 2>/dev/null && info "已停止后端进程" || true
pkill -f "vite" 2>/dev/null && info "已停止前端进程" || true

info "全部停止。"
