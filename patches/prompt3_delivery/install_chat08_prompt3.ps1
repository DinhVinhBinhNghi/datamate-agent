param([string]$ProjectRoot = 'D:\ZALO')
$ErrorActionPreference = 'Stop'
$package = Split-Path -Parent $MyInvocation.MyCommand.Path
$payload = Join-Path $package 'payload'
$parent = Join-Path $ProjectRoot 'artifacts\submissions\submission_wave1_public_revenue_20261030_220018.jsonl'
$baseline = Join-Path $ProjectRoot 'artifacts\submissions\submission_chat07_public_20261030_181131.jsonl'
if ((Get-FileHash $parent -Algorithm SHA256).Hash.ToLower() -ne '0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a') { throw 'Candidate B hash mismatch' }
if ((Get-FileHash $baseline -Algorithm SHA256).Hash.ToLower() -ne 'c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6') { throw 'Baseline hash mismatch' }
$backup = Join-Path $ProjectRoot ('artifacts\rollback\chat08_prompt3_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force $backup | Out-Null
foreach ($item in Get-ChildItem $payload -File -Recurse) {
  $relative = $item.FullName.Substring($payload.Length).TrimStart('\','/')
  $target = Join-Path $ProjectRoot $relative
  if (Test-Path $target) {
    $saved = Join-Path $backup $relative
    New-Item -ItemType Directory -Force (Split-Path $saved -Parent) | Out-Null
    Copy-Item -LiteralPath $target -Destination $saved
  }
  New-Item -ItemType Directory -Force (Split-Path $target -Parent) | Out-Null
  Copy-Item -LiteralPath $item.FullName -Destination $target
}
Write-Host "Installed. Rollback: $backup"
