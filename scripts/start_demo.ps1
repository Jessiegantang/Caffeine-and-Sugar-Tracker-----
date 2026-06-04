$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"

Write-Host "Starting DrinkMind backend on http://127.0.0.1:8000"
Start-Process -WindowStyle Hidden -WorkingDirectory $backend -FilePath (Join-Path $backend "venv\Scripts\python.exe") -ArgumentList @("-m", "uvicorn", "main:app", "--reload")

Write-Host "Starting DrinkMind frontend. Use the Vite URL printed in this terminal."
Set-Location $root
npm.cmd run dev
