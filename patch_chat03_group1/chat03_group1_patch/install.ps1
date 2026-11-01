param(
    [string]$ProjectRoot = "D:\ZALO"
)

$ErrorActionPreference = "Stop"
$patchRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

$targets = @(
    @{ Source = "src\datamate\__init__.py"; Destination = "src\datamate\__init__.py" },
    @{ Source = "src\datamate\load_business.py"; Destination = "src\datamate\load_business.py" },
    @{ Source = "configs\businesses\train\biz_129.json"; Destination = "configs\businesses\train\biz_129.json" }
)

foreach ($item in $targets) {
    $sourcePath = Join-Path $patchRoot $item.Source
    $destinationPath = Join-Path $ProjectRoot $item.Destination
    $destinationDirectory = Split-Path -Parent $destinationPath
    New-Item -ItemType Directory -Force -Path $destinationDirectory | Out-Null
    Copy-Item -LiteralPath $sourcePath -Destination $destinationPath -Force
    Write-Output "Installed $($item.Destination)"
}

Write-Output "Patch installed. Raw data was not modified."
