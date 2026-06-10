$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$env:ENABLE_LLM = "false"
$env:DRINKMIND_OFFLINE = "true"

function Invoke-Step {
    param(
        [string]$Title,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "============================================================"
    Write-Host $Title
    Write-Host "============================================================"

    & $Command
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Error "$Title failed with exit code $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

Invoke-Step "1. Backend unittest" {
    Push-Location $BackendDir
    try {
        & ".\venv\Scripts\python.exe" -m unittest discover -s tests
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "2. Composition eval report" {
    Push-Location $BackendDir
    try {
        & ".\venv\Scripts\python.exe" "tests\run_composition_eval_report.py"
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "3. Frontend build" {
    Push-Location $RootDir
    try {
        & npm.cmd run build
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Quality gate passed."
