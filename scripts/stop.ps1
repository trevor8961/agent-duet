# agent-duet 一键停止（Windows PowerShell 原生）。幂等。

$Root = Split-Path -Parent $PSScriptRoot
$RunDir = Join-Path $Root ".run"

function Info($msg) { Write-Host "[agent-duet] $msg" -ForegroundColor Cyan }

# 按 PID 文件停
foreach ($name in @("backend", "frontend")) {
  $pidfile = Join-Path $RunDir "$name.pid"
  if (Test-Path $pidfile) {
    $pid = Get-Content $pidfile
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue; Info "已停止 $name（pid $pid）" }
    Remove-Item $pidfile -ErrorAction SilentlyContinue
  }
}

# 兜底：按命令行匹配停
Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe'" |
  Where-Object { $_.CommandLine -match "uvicorn app.main|vite" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Info "已停止进程 $($_.ProcessId)" }

Info "全部停止。"
