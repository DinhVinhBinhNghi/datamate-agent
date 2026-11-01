param([string]$ProjectRoot = "D:\ZALO")
$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
  "src\datamate\evaluate_planner.py",
  "tests\planner\fixtures\oracle_intents_dev.jsonl",
  "tests\planner\test_evaluation.py"
)
foreach ($relative in $files) {
  $src = Join-Path $patchRoot $relative
  $dst = Join-Path $ProjectRoot $relative
  if (-not (Test-Path -LiteralPath $src)) { throw "Missing patch file: $relative" }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Output "Installed $relative"
}
