param([string]$ProjectRoot = "D:\ZALO")
$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
  "src\datamate\planner\__init__.py",
  "src\datamate\planner\schema.py",
  "src\datamate\planner\validate.py",
  "src\datamate\planner\heuristic.py",
  "src\datamate\planner\intent.schema.json",
  "src\datamate\plan_question.py",
  "tests\planner\test_group1.py",
  "tests\planner\fixtures\valid_intent.json",
  "tests\planner\fixtures\valid_plan.json",
  "tests\planner\fixtures\invalid_plans.jsonl"
)
foreach ($relative in $files) {
  $src = Join-Path $patchRoot $relative
  $dst = Join-Path $ProjectRoot $relative
  if (-not (Test-Path -LiteralPath $src)) { throw "Missing patch file: $relative" }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Output "Installed $relative"
}
