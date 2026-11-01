param([string]$ProjectRoot = 'D:\ZALO', [string]$RunId = '', [switch]$Resume)
$ErrorActionPreference = 'Stop'
if (-not $RunId) { $RunId = 'chat08_expansion_' + (Get-Date -Format 'yyyyMMdd_HHmmss') }
$python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$args = @('-m','datamate.chat08.run_expansion','--project-root',$ProjectRoot,'--run-id',$RunId)
if ($Resume) { $args += '--resume' }
& $python @args
if ($LASTEXITCODE -ne 0) { throw "Expansion failed with exit code $LASTEXITCODE" }
Write-Host "Run complete: $ProjectRoot\artifacts\runs\$RunId\expansion_manifest.json"
Write-Host 'Candidates were created locally only; nothing was submitted.'
