param([string]$ProjectRoot = "D:\ZALO")
$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$files = @(
  "src\datamate\business\revenue.py",
  "configs\businesses\train\biz_129.json",
  "tests\test_revenue.py"
)
foreach ($relative in $files) {
  $src = Join-Path $patchRoot $relative
  $dst = Join-Path $ProjectRoot $relative
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
  Write-Output "Installed $relative"
}
