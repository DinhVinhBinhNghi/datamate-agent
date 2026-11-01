$ErrorActionPreference = 'Stop'
$root = 'D:\ZALO'
$last = Join-Path $root 'artifacts\rollback\chat07_group2_last.txt'
if (-not (Test-Path -LiteralPath $last)) { throw 'No Chat 07 Group 2 rollback snapshot found.' }
$backup = (Get-Content -LiteralPath $last -Raw).Trim()
$manifestPath = Join-Path $backup 'install_manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw "Missing rollback manifest: $manifestPath" }
$entries = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
foreach ($entry in $entries) {
    $target = Join-Path $root $entry.path
    if ($entry.existed) {
        $saved = Join-Path $backup $entry.path
        if (-not (Test-Path -LiteralPath $saved)) { throw "Missing rollback file: $saved" }
        Copy-Item -LiteralPath $saved -Destination $target -Force
        Write-Host "Restored $($entry.path)"
    } elseif (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Force
        Write-Host "Removed newly installed $($entry.path)"
    }
}
