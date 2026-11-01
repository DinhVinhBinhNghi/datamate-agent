param([string]$ProjectRoot = 'D:\ZALO')
$ErrorActionPreference = 'Stop'
$expected = @{
  'submission_chat07_public_20261030_181131.jsonl'='c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6';
  'submission_wave1_public_revenue_20261030_220018.jsonl'='0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a'
}
foreach ($name in $expected.Keys) {
  $path = Join-Path $ProjectRoot "artifacts\submissions\$name"
  $actual = (Get-FileHash $path -Algorithm SHA256).Hash.ToLower()
  if ($actual -ne $expected[$name]) { throw "Hash mismatch: $name" }
  Write-Host "PASS hash $name $actual"
}
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
& $python -m unittest discover -s (Join-Path $ProjectRoot 'tests\chat08_expansion') -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
Write-Host 'PASS: no leaderboard submission action exists in this patch.'
