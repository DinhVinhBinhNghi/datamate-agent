param([string]$ProjectRoot = "D:\ZALO")
$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
  "src\datamate\run.py",
  "src\datamate\validate_submission.py",
  "src\datamate\validation\__init__.py",
  "src\datamate\validation\gates.py",
  "src\datamate\format\__init__.py",
  "src\datamate\format\answer.py",
  "tests\pipeline\test_gates_formatter.py"
)
foreach ($relative in $files) {
  $src = Join-Path $patchRoot $relative
  $dst = Join-Path $ProjectRoot $relative
  if (-not (Test-Path -LiteralPath $src)) { throw "Missing patch file: $relative" }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Output "Installed $relative"
}
