$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv-next\Scripts\python.exe'
$runDir = Join-Path $projectDir 'next_data\run'
$logDir = Join-Path $projectDir 'next_data\logs'

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Run setup first: python -m venv .venv-next and install next_requirements.txt'
}

New-Item -ItemType Directory -Path $runDir -Force | Out-Null
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Start-NeuralProcess {
    param([string]$Name, [string[]]$Arguments)
    $pidFile = Join-Path $runDir "$Name.pid"
    if (Test-Path -LiteralPath $pidFile) {
        $oldPid = [int](Get-Content -LiteralPath $pidFile -Raw)
        if (Get-Process -Id $oldPid -ErrorAction SilentlyContinue) { return }
    }
    $stdout = Join-Path $logDir "$Name.out.log"
    $stderr = Join-Path $logDir "$Name.err.log"
    $process = Start-Process -FilePath $pythonExe -ArgumentList $Arguments -WorkingDirectory $projectDir `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii
}

$env:PUBLIC_BASE_URL = 'http://127.0.0.1:8765'
Start-NeuralProcess -Name 'neural-api' -Arguments @('-m', 'uvicorn', 'neural.api:create_app', '--factory', '--host', '127.0.0.1', '--port', '8765')
Start-NeuralProcess -Name 'upbit-collector' -Arguments @('-m', 'neural.collector')
Start-NeuralProcess -Name 'binance-futures-collector' -Arguments @('-m', 'neural.binance_futures')
Write-Output 'Neural Trade started: http://127.0.0.1:8765'
