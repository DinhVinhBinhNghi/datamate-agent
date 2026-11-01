$ErrorActionPreference = 'Stop'
$root = 'D:\ZALO'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $root "artifacts\rollback\chat07_group2_$stamp"
$entries = @()

function Install-Tree($sourceRoot, $targetRoot, $projectPrefix) {
    $files = Get-ChildItem -Path $sourceRoot -Recurse -File
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($sourceRoot.Length).TrimStart('\')
        $target = Join-Path $targetRoot $relative
        $projectRelative = Join-Path $projectPrefix $relative
        $existed = Test-Path -LiteralPath $target
        if ($existed) {
            $backupTarget = Join-Path $backup $projectRelative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupTarget) | Out-Null
            Copy-Item -LiteralPath $target -Destination $backupTarget -Force
        }
        $script:entries += [pscustomobject]@{ path = $projectRelative; existed = $existed }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $target -Force
        Write-Host "Installed $projectRelative"
    }
}

Install-Tree (Join-Path $here 'src') (Join-Path $root 'src') 'src'
Install-Tree (Join-Path $here 'configs') (Join-Path $root 'configs') 'configs'
Install-Tree (Join-Path $here 'tests') (Join-Path $root 'tests') 'tests'

New-Item -ItemType Directory -Force -Path $backup | Out-Null
$entries | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $backup 'install_manifest.json') -Encoding UTF8
$last = Join-Path $root 'artifacts\rollback\chat07_group2_last.txt'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $last) | Out-Null
Set-Content -LiteralPath $last -Value $backup -Encoding UTF8
Write-Host "Rollback snapshot: $backup"
