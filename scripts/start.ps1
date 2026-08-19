# agent-duet 一键启动（Windows PowerShell 原生）
# 装依赖（如缺）→ 起后端 → 起前端 → 打开浏览器。幂等。

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BackendPort = 8300
$FrontendPort = 5173
$RunDir = Join-Path $Root ".run"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

function Info($msg) { Write-Host "[agent-duet] $msg" -ForegroundColor Cyan }
function Err($msg)  { Write-Host "[agent-duet] $msg" -ForegroundColor Red }

# ── 前置检查 ──
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { Err "缺少 uv（https://docs.astral.sh/uv/）"; exit 1 }
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { Err "缺少 Node 18+"; exit 1 }
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { Err "缺少 claude code"; exit 1 }

function Test-Port($port) {
  try {
    $r = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2
    return $true
  } catch { return $false }
}

# ── 依赖安装（仅首次）──
if (-not (Test-Path (Join-Path $Root "backend\.venv"))) {
  Info "首次运行：安装后端依赖…"
  Push-Location (Join-Path $Root "backend"); uv sync; Pop-Location
}
if (-not (Test-Path (Join-Path $Root "frontend\node_modules"))) {
  Info "首次运行：安装前端依赖…"
  Push-Location (Join-Path $Root "frontend"); npm install; Pop-Location
}

# ── 后端 ──
if (Test-Port $BackendPort) {
  Info "后端已在运行（端口 $BackendPort）"
} else {
  Info "启动后端（端口 $BackendPort）…"
  $backend = Start-Process -FilePath "uv" -ArgumentList "run","uvicorn","app.main:app","--port","$BackendPort" `
    -WorkingDirectory (Join-Path $Root "backend") -RedirectStandardOutput (Join-Path $RunDir "backend.log") `
    -RedirectStandardError (Join-Path $RunDir "backend.err") -WindowStyle Hidden -PassThru
  $backend.Id | Out-File (Join-Path $RunDir "backend.pid")
}

# ── 前端 ──
if (Test-Port $FrontendPort) {
  Info "前端已在运行（端口 $FrontendPort）"
} else {
  Info "启动前端（端口 $FrontendPort）…"
  $frontend = Start-Process -FilePath "npm" -ArgumentList "run","dev" `
    -WorkingDirectory (Join-Path $Root "frontend") -RedirectStandardOutput (Join-Path $RunDir "frontend.log") `
    -RedirectStandardError (Join-Path $RunDir "frontend.err") -WindowStyle Hidden -PassThru
  $frontend.Id | Out-File (Join-Path $RunDir "frontend.pid")
}

# ── 打开浏览器 ──
Start-Sleep -Seconds 2
Info "打开 http://localhost:$FrontendPort"
Start-Process "http://localhost:$FrontendPort"

Info "完成。停止：.\scripts\stop.ps1"
