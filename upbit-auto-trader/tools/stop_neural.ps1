$projectDir = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $projectDir 'next_data\run'
foreach ($name in @('neural-api', 'upbit-collector', 'binance-futures-collector')) {
    $pidFile = Join-Path $runDir "$name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $processId = [int](Get-Content -LiteralPath $pidFile -Raw)
    $children = Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $processId }
    foreach ($child in $children) {
        Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
    }
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process) { Stop-Process -Id $processId -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $pidFile -Force
}
Write-Output 'Neural Trade stopped.'
