$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv-next\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Missing .venv-next. Create a Python 3.11 virtual environment and install next_requirements.txt.'
}

Push-Location $projectDir
try {
    & $pythonExe -m neural.preflight
    & (Join-Path $PSScriptRoot 'start_neural.ps1')
    Write-Output 'Read SESSION_HANDOFF.md before making changes.'
} finally {
    Pop-Location
}
