#!/usr/bin/env bash
# agent-duet 一键启动：装依赖（如缺）→ 起后端 → 起前端 → 打开浏览器。
# 幂等：已在运行的进程不会重复启动。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PORT=8300
FRONTEND_PORT=5173
RUN_DIR="${ROOT}/.run"

mkdir -p "${RUN_DIR}"

info() { printf '\033[1;34m[agent-duet]\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31m[agent-duet]\033[0m %s\n' "$1" >&2; }

# ── 前置检查 ──
command -v uv >/dev/null 2>&1 || { err "缺少 uv（https://docs.astral.sh/uv/）"; exit 1; }
command -v node >/dev/null 2>&1 || { err "缺少 Node 18+"; exit 1; }
command -v claude >/dev/null 2>&1 || { err "缺少 claude code（agent-duet 的目标 agent）"; exit 1; }

# ── 依赖安装（仅首次）──
if [ ! -d "${ROOT}/backend/.venv" ]; then
  info "首次运行：安装后端依赖…"
  (cd "${ROOT}/backend" && uv sync)
fi
if [ ! -d "${ROOT}/frontend/node_modules" ]; then
  info "首次运行：安装前端依赖…"
  (cd "${ROOT}/frontend" && npm install)
fi

# ── 后端 ──
if curl -s -o /dev/null "http://localhost:${BACKEND_PORT}/api/health"; then
  info "后端已在运行（端口 ${BACKEND_PORT}）"
else
  info "启动后端（端口 ${BACKEND_PORT}）…"
  (cd "${ROOT}/backend" && nohup uv run uvicorn app.main:app --port ${BACKEND_PORT} \
    > "${RUN_DIR}/backend.log" 2>&1 & echo $! > "${RUN_DIR}/backend.pid")
  # 等待健康检查就绪
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "http://localhost:${BACKEND_PORT}/api/health" && break
    sleep 1
  done
fi

# ── 前端 ──
if curl -s -o /dev/null "http://localhost:${FRONTEND_PORT}"; then
  info "前端已在运行（端口 ${FRONTEND_PORT}）"
else
  info "启动前端（端口 ${FRONTEND_PORT}）…"
  (cd "${ROOT}/frontend" && nohup npm run dev \
    > "${RUN_DIR}/frontend.log" 2>&1 & echo $! > "${RUN_DIR}/frontend.pid")
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "http://localhost:${FRONTEND_PORT}" && break
    sleep 1
  done
fi

# ── 打开浏览器 ──
info "打开 http://localhost:${FRONTEND_PORT}"
case "$(uname -s)" in
  Darwin) open "http://localhost:${FRONTEND_PORT}" ;;
  Linux)  xdg-open "http://localhost:${FRONTEND_PORT}" >/dev/null 2>&1 || true ;;
esac

info "完成。日志：backend.log / frontend.log（在 ${RUN_DIR}）"
info "停止：./scripts/stop.sh"
