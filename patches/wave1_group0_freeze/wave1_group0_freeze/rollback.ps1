param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Pointer = Join-Path $ProjectRoot 'artifacts\snapshots\wave1_prechange_last.txt'
if (-not (Test-Path -LiteralPath $Pointer)) { throw "Snapshot pointer not found: $Pointer" }
$Snapshot = (Get-Content -LiteralPath $Pointer -Raw -Encoding UTF8).Trim()
if (-not (Test-Path -LiteralPath (Join-Path $Snapshot 'freeze_manifest.json'))) {
    throw "Invalid Wave 1 snapshot: $Snapshot"
}
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Recovery = Join-Path $ProjectRoot "artifacts\rollback\wave1_current_before_restore_$Stamp"
New-Item -ItemType Directory -Force -Path $Recovery | Out-Null

foreach ($RelativePath in @('src','configs','tests')) {
    $Current = Join-Path $ProjectRoot $RelativePath
    $SavedCurrent = Join-Path $Recovery $RelativePath
    if (Test-Path -LiteralPath $Current) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $SavedCurrent) | Out-Null
        Move-Item -LiteralPath $Current -Destination $SavedCurrent
    }
    Copy-Item -LiteralPath (Join-Path $Snapshot $RelativePath) -Destination $Current -Recurse
}

Copy-Item -LiteralPath (Join-Path $Snapshot 'metadata\submission_log.csv') `
    -Destination (Join-Path $ProjectRoot 'artifacts\leaderboard\submission_log.csv') -Force
Copy-Item -LiteralPath (Join-Path $Snapshot 'metadata\chat07_handoff.md') `
    -Destination (Join-Path $ProjectRoot 'handoffs\chat07_handoff.md') -Force

Write-Host "Restored pre-Wave-1 source/config/tests and metadata from: $Snapshot"
Write-Host "Previous current state was preserved at: $Recovery"
Write-Host 'The immutable baseline submission was not modified.'
