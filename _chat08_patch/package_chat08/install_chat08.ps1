param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Rollback = Join-Path $ProjectRoot "artifacts\rollback\chat08_audit_$Stamp"

$Files = @(
    'src\datamate\chat08\__init__.py',
    'src\datamate\chat08\inventory.py',
    'src\datamate\chat08\archetypes.py',
    'src\datamate\chat08\prioritize.py',
    'src\datamate\chat08\reporting.py',
    'src\datamate\chat08\run_all.py',
    'tests\chat08\test_inventory.py'
)

foreach ($Relative in $Files) {
    $Source = Join-Path $Here $Relative
    if (-not (Test-Path -LiteralPath $Source)) { throw "Patch file missing: $Relative" }
    $Target = Join-Path $ProjectRoot $Relative
    if (Test-Path -LiteralPath $Target) {
        $Backup = Join-Path $Rollback $Relative
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Backup) | Out-Null
        Copy-Item -LiteralPath $Target -Destination $Backup -Force
    }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Target -Force
}

$ArtifactSource = Join-Path $Here 'artifacts\chat08'
$ArtifactTarget = Join-Path $ProjectRoot 'artifacts\chat08'
if (Test-Path -LiteralPath $ArtifactTarget) {
    New-Item -ItemType Directory -Force -Path $Rollback | Out-Null
    Copy-Item -LiteralPath $ArtifactTarget -Destination (Join-Path $Rollback 'artifacts\chat08') -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ArtifactTarget | Out-Null
Copy-Item -Path (Join-Path $ArtifactSource '*') -Destination $ArtifactTarget -Recurse -Force

[ordered]@{
    passed = $true
    project_root = $ProjectRoot
    rollback = $Rollback
    installed_code_files = $Files.Count
    artifact_directory = $ArtifactTarget
    submissions_touched = $false
} | ConvertTo-Json -Depth 3
