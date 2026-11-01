param(
    [string]$ProjectRoot = "D:\ZALO"
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$relativeFiles = @(
    "src\datamate\load_business.py",
    "src\datamate\cache.py",
    "src\datamate\benchmark_cache.py"
)

foreach ($relativePath in $relativeFiles) {
    $sourcePath = Join-Path $patchRoot $relativePath
    $destinationPath = Join-Path $ProjectRoot $relativePath
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $destinationPath) | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    Write-Output "Installed $relativePath"
}

Write-Output "Cache benchmark patch installed. Raw data was not modified."
