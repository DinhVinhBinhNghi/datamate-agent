$ErrorActionPreference = 'Stop'
$root = 'D:\ZALO'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $here 'tests\pipeline\test_chat07_dev002.py'
$target = Join-Path $root 'tests\pipeline\test_chat07_dev002.py'
if (-not (Test-Path -LiteralPath $source)) { throw "Missing hotfix source: $source" }
Copy-Item -LiteralPath $source -Destination $target -Force
Write-Host 'Installed tests\pipeline\test_chat07_dev002.py'
