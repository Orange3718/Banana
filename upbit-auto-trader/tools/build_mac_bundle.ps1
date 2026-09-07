$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$artifactDir = Join-Path $projectDir 'artifacts'
$stageDir = Join-Path $artifactDir "upbit-auto-trader-mac-$stamp"
$zipFile = "$stageDir.zip"

New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

function Copy-ProjectFile {
    param([string]$RelativePath)
    $source = Join-Path $projectDir $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { return }
    $target = Join-Path $stageDir $RelativePath
    New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $target
}

function Copy-ProjectTree {
    param([string]$RelativeRoot)
    $sourceRoot = Join-Path $projectDir $RelativeRoot
    if (-not (Test-Path -LiteralPath $sourceRoot)) { return }
    Get-ChildItem -LiteralPath $sourceRoot -File -Recurse | Where-Object {
        $_.FullName -notmatch '[\\/](node_modules|__pycache__|\.pytest_cache)[\\/]'
    } | ForEach-Object {
        $relative = $_.FullName.Substring($projectDir.Length + 1)
        Copy-ProjectFile $relative
    }
}

foreach ($tree in @('neural', 'apps\dashboard', 'deploy', 'tests_next')) {
    Copy-ProjectTree $tree
}

Get-ChildItem -LiteralPath $projectDir -File | Where-Object {
    $_.Extension -in @('.py', '.md', '.json', '.txt', '.command') -or
    $_.Name -in @('.env.example', '.gitignore', '.dockerignore')
} | ForEach-Object { Copy-ProjectFile $_.Name }

foreach ($script in @('setup_macos.sh', 'start_neural.sh', 'stop_neural.sh', 'resume_session.sh',
                      'start_neural.ps1', 'stop_neural.ps1', 'resume_session.ps1', 'save_session.ps1')) {
    Copy-ProjectFile (Join-Path 'tools' $script)
}

$migrationDir = Join-Path $stageDir 'migration'
New-Item -ItemType Directory -Path $migrationDir -Force | Out-Null
$exportFile = Join-Path $migrationDir 'neural-export.json'
$pythonExe = Join-Path $projectDir '.venv-next\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv-next Python runtime.' }
Push-Location $projectDir
try {
    & $pythonExe -m neural.manage export --file $exportFile
} finally {
    Pop-Location
}

$secretFiles = Get-ChildItem -LiteralPath $stageDir -File -Recurse | Where-Object {
    $_.Name -eq '.env' -or $_.Name -match '\.(pem|key)$'
}
if ($secretFiles) { throw 'Secret-like files found in staging directory.' }

Compress-Archive -LiteralPath $stageDir -DestinationPath $zipFile -CompressionLevel Optimal
Write-Output "Mac migration bundle: $zipFile"
Write-Output 'Credentials are excluded. The migration export contains account history and must be protected.'
