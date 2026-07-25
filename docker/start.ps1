$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location $projectRoot

try {
    docker build -f docker/backend.Dockerfile -t drinkmind-backend:local .
    if ($LASTEXITCODE -ne 0) {
        throw "Backend image build failed."
    }

    docker build -f docker/frontend.Dockerfile -t drinkmind-frontend:local .
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend image build failed."
    }

    docker compose -f docker/compose.yaml up -d --no-build
    if ($LASTEXITCODE -ne 0) {
        throw "DrinkMind containers failed to start."
    }
}
finally {
    Pop-Location
}
