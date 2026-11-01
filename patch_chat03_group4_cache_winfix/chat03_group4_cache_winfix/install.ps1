param(
    [string]$ProjectRoot = "D:\ZALO"
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$relativePath = "src\datamate\cache.py"
$sourcePath = Join-Path $patchRoot $relativePath
$destinationPath = Join-Path $ProjectRoot $relativePath
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destinationPath) | Out-Null
Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
Write-Output "Installed $relativePath"
Write-Output "Windows atomic-cache lock fix installed."
