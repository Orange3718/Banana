$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv-next\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv-next Python runtime.' }
Push-Location $projectDir
try {
    & $pythonExe -m pytest tests_next -q
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; session bundle was not created.' }
    & (Join-Path $PSScriptRoot 'build_mac_bundle.ps1')
    if ($LASTEXITCODE -ne 0) { throw 'Bundle creation failed.' }
    Write-Output 'Session saved. Keep SESSION_HANDOFF.md with the newest ZIP.'
} finally {
    Pop-Location
}
