param(
    [string]$ProjectRoot = "D:\ZALO"
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$relativeFiles = @(
    "src\datamate\__init__.py",
    "src\datamate\load_business.py",
    "src\datamate\readers.py",
    "src\datamate\joins.py",
    "src\datamate\smoke_pipeline.py",
    "configs\businesses\train\biz_129.json",
    "configs\businesses\train\biz_116.json",
    "configs\businesses\train\biz_123.json",
    "tests\test_direct_readers.py",
    "tests\test_join_helper.py"
)

foreach ($relativePath in $relativeFiles) {
    $sourcePath = Join-Path $patchRoot $relativePath
    $destinationPath = Join-Path $ProjectRoot $relativePath
    $destinationDirectory = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    Write-Output "Installed $relativePath"
}

Write-Output "Group 3 patch installed. Raw data was not modified."
