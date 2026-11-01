param([string]$ProjectRoot = 'D:\ZALO')
$ErrorActionPreference = 'Stop'
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $patchRoot 'payload'
$baseline = Join-Path $ProjectRoot 'artifacts\submissions\submission_chat07_public_20261030_181131.jsonl'
$parent = Join-Path $ProjectRoot 'artifacts\submissions\submission_wave1_public_revenue_20261030_220018.jsonl'
if (-not (Test-Path $baseline) -or -not (Test-Path $parent)) { throw 'Frozen baseline or Candidate B is missing.' }
if ((Get-FileHash $baseline -Algorithm SHA256).Hash.ToLower() -ne 'c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6') { throw 'Baseline hash mismatch.' }
if ((Get-FileHash $parent -Algorithm SHA256).Hash.ToLower() -ne '0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a') { throw 'Candidate B hash mismatch.' }
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $ProjectRoot "artifacts\backups\chat08_prompt2_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$files = Get-ChildItem -Path $payload -Recurse -File
foreach ($file in $files) {
  $relative = $file.FullName.Substring($payload.Length).TrimStart('\','/')
  $target = Join-Path $ProjectRoot $relative
  if (Test-Path $target) {
    $backupTarget = Join-Path $backup $relative
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $backupTarget) | Out-Null
    Copy-Item -LiteralPath $target -Destination $backupTarget -Force
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target) | Out-Null
  Copy-Item -LiteralPath $file.FullName -Destination $target -Force
}
@{ installed_at = (Get-Date).ToString('o'); backup = $backup; file_count = $files.Count } |
  ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $ProjectRoot 'artifacts\chat08\prompt2_install.json')
Write-Host "Installed $($files.Count) files. Backup: $backup"
Write-Host 'Raw train/public files and frozen submissions were not modified.'
