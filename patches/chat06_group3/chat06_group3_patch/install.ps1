param([string]$ProjectRoot = "D:\ZALO")
$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
  "src\datamate\eval\__init__.py",
  "src\datamate\eval\metrics.py",
  "src\datamate\eval\scorer.py",
  "src\datamate\eval\runner.py",
  "tests\pipeline\test_eval.py"
)
foreach ($relative in $files) {
  $src = Join-Path $patchRoot $relative
  $dst = Join-Path $ProjectRoot $relative
  if (-not (Test-Path -LiteralPath $src)) { throw "Missing patch file: $relative" }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Output "Installed $relative"
}
