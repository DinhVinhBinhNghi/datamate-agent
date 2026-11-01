param([string]$ProjectRoot = 'D:\ZALO', [string]$RunId = '')
$ErrorActionPreference = 'Stop'
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
& $python -m unittest discover -s (Join-Path $ProjectRoot 'tests\chat08_expansion') -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
if ($RunId) {
  $manifest = Get-Content (Join-Path $ProjectRoot "artifacts\runs\$RunId\expansion_manifest.json") -Raw | ConvertFrom-Json
  if (-not $manifest.passed -or -not $manifest.hashes_unchanged_after -or -not $manifest.code_config_freeze_unchanged) { throw 'Manifest gate failed' }
  foreach ($candidate in $manifest.candidates) {
    if ($candidate.created -and (-not $candidate.validation.valid -or $candidate.diff.Count -ne $candidate.change_count)) { throw "Candidate diff failed: $($candidate.candidate)" }
  }
}
Write-Host 'Verification passed; no leaderboard submission performed.'
