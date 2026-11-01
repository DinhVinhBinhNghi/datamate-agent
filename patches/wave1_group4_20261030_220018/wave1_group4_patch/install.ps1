param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $ProjectRoot "artifacts\rollback\wave1_group4_$Stamp"
$Entries = @()

function Install-Tree([string]$SourceRoot, [string]$TargetRoot, [string]$Prefix) {
    foreach ($File in Get-ChildItem -LiteralPath $SourceRoot -Recurse -File) {
        $Relative = $File.FullName.Substring($SourceRoot.Length).TrimStart('\')
        $Target = Join-Path $TargetRoot $Relative
        $ProjectRelative = Join-Path $Prefix $Relative
        $Existed = Test-Path -LiteralPath $Target
        if ($Existed) {
            $Saved = Join-Path $Backup $ProjectRelative
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Saved) | Out-Null
            Copy-Item -LiteralPath $Target -Destination $Saved -Force
        }
        $script:Entries += [pscustomobject]@{ path = $ProjectRelative; existed = $Existed }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
        Copy-Item -LiteralPath $File.FullName -Destination $Target -Force
        Write-Host "Installed $ProjectRelative"
    }
}

Install-Tree (Join-Path $Here 'src') (Join-Path $ProjectRoot 'src') 'src'
Install-Tree (Join-Path $Here 'configs') (Join-Path $ProjectRoot 'configs') 'configs'
Install-Tree (Join-Path $Here 'tests') (Join-Path $ProjectRoot 'tests') 'tests'
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
$Entries | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $Backup 'install_manifest.json') -Encoding UTF8
Set-Content -LiteralPath (Join-Path $ProjectRoot 'artifacts\rollback\wave1_group4_last.txt') -Value $Backup -Encoding UTF8
Write-Host "Rollback snapshot: $Backup"
