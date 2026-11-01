param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Pointer = Join-Path $ProjectRoot 'artifacts\rollback\wave1_group4_last.txt'
if (-not (Test-Path -LiteralPath $Pointer)) { throw "Rollback pointer not found: $Pointer" }
$Backup = (Get-Content -LiteralPath $Pointer -Raw -Encoding UTF8).Trim()
$ManifestPath = Join-Path $Backup 'install_manifest.json'
if (-not (Test-Path -LiteralPath $ManifestPath)) { throw "Rollback manifest not found: $ManifestPath" }
$Entries = @(Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json)
foreach ($Entry in $Entries) {
    $Target = Join-Path $ProjectRoot $Entry.path
    if ($Entry.existed) {
        Copy-Item -LiteralPath (Join-Path $Backup $Entry.path) -Destination $Target -Force
    } elseif (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Force
    }
    Write-Host "Restored $($Entry.path)"
}
Write-Host 'Wave 1 Group 4 code/config rolled back to Group 3. Generated candidates and the frozen baseline were preserved.'
