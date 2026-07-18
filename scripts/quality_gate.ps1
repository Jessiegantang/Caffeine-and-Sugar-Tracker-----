$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"
$TempRunDir = Join-Path $env:TEMP ("drinkmind-quality-gate-" + [guid]::NewGuid().ToString("N"))
$TempDbPath = Join-Path $TempRunDir "test_drinks.db"
$TempChromaDir = Join-Path $TempRunDir "chroma_db"
$TempDistDir = Join-Path $TempRunDir "dist"

New-Item -ItemType Directory -Path $TempRunDir | Out-Null

$env:ENABLE_LLM = "false"
$env:DRINKMIND_OFFLINE = "true"
$env:DATABASE_URL = "sqlite:///$($TempDbPath.Replace('\', '/'))"
$env:CHROMA_PERSIST_DIR = $TempChromaDir

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

try {
    Invoke-Step "0. Init temp database schema" {
        Push-Location $BackendDir
        try {
            & ".\venv\Scripts\python.exe" -c "from db.database import Base, engine; Base.metadata.create_all(bind=engine)"
        }
        finally {
            Pop-Location
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

    Invoke-Step "3. Agent effect eval report" {
        Push-Location $BackendDir
        try {
            & ".\venv\Scripts\python.exe" "tests\run_agent_effect_eval_report.py"
        }
        finally {
            Pop-Location
        }
    }

    Invoke-Step "4. Frontend build" {
        Push-Location $FrontendDir
        try {
            & npm.cmd run build -- --outDir $TempDistDir
        }
        finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "Quality gate passed."
}
finally {
    if (Test-Path $TempRunDir) {
        Remove-Item -Recurse -Force $TempRunDir
    }
}
