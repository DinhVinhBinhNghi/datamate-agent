param([Parameter(Mandatory=$true)][string]$ProjectRoot,[Parameter(Mandatory=$true)][string]$PatchRoot)
$ErrorActionPreference='Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Accept either the extracted `patch` directory or its parent delivery directory.
if (!(Test-Path (Join-Path $PatchRoot 'chat09_raw.py')) -and (Test-Path (Join-Path $PatchRoot 'patch\chat09_raw.py'))) {
    $PatchRoot = Join-Path $PatchRoot 'patch'
}
if (!(Test-Path (Join-Path $PatchRoot 'chat09_raw.py'))) {
    throw "Patch files not found under $PatchRoot. Expected chat09_raw.py beside this script or in a patch subdirectory."
}
$expected=@{
 'submission_chat07_public_20261030_181131.jsonl'='c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6'
 'submission_wave1_public_revenue_20261030_220018.jsonl'='0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a'
 'submission_chat08_prompt3_20261031_221000_candidate_g_growth_percent.jsonl'='3af7a104c16e41249419c9cc9260ac68ef80c68141e8df32b4af2880952b88dd'
}
$artifact=Join-Path $ProjectRoot 'artifacts\chat09';New-Item -ItemType Directory -Force $artifact | Out-Null
$checkpoint=Join-Path $artifact 'STATE.md'
foreach($item in $expected.GetEnumerator()) {
 $p=Join-Path $ProjectRoot ('artifacts\submissions\'+$item.Key)
 if(!(Test-Path $p)){throw "Frozen parent missing: $p"}
 $actual=(Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant()
 if($actual -ne $item.Value){throw "Frozen hash mismatch: $p $actual"}
}
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$snapshot=Join-Path $ProjectRoot ('artifacts\rollback\chat09_'+$stamp)
New-Item -ItemType Directory -Force $snapshot | Out-Null
foreach($part in @('src','configs','tests')) {
 $src=Join-Path $ProjectRoot $part
 if(Test-Path $src){Copy-Item $src (Join-Path $snapshot $part) -Recurse}
}
$files=Get-ChildItem $snapshot -Recurse -File | ForEach-Object { [pscustomobject]@{ Path=$_.FullName; SHA256=(Get-FileHash $_.FullName -Algorithm SHA256).Hash } }
$files | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $snapshot 'snapshot_hashes.json') -Encoding utf8
"# Chat09 Windows checkpoint`n`nFrozen hashes verified. Snapshot: $snapshot. No frozen file modified. Next: raw audit and J builder.`n" | Set-Content $checkpoint -Encoding utf8
$python=Join-Path $ProjectRoot '.venv\Scripts\python.exe';if(!(Test-Path $python)){throw 'Python venv missing'}
& $python (Join-Path $PatchRoot 'chat09_raw.py') --root $ProjectRoot --out $artifact
if($LASTEXITCODE -ne 0){throw 'Raw audit failed'}
& $python (Join-Path $PatchRoot 'chat09_matrix.py') --root $ProjectRoot --out $artifact
if($LASTEXITCODE -ne 0){throw 'Matrix failed'}
& $python (Join-Path $PatchRoot 'sqlite_sales_view.py') --root $ProjectRoot --out $artifact
if($LASTEXITCODE -ne 0){throw 'POS view audit failed'}
$parent=Join-Path $ProjectRoot 'artifacts\submissions\submission_chat08_prompt3_20261031_221000_candidate_g_growth_percent.jsonl'
# build_j refuses existing candidate/manifest; resume safely after inspecting the existing checkpoint.
& $python (Join-Path $PatchRoot 'build_j.py') --root $ProjectRoot --parent $parent --output-dir $artifact
if($LASTEXITCODE -ne 0){throw 'J build failed; inspect checkpoint before rerun'}
"`nJ built with local structural checks. Run existing official validator against candidate_j_from_g.jsonl and record result; then review diff/manifest. K/L/M/N remain blocked by their specific train/public gates.`n" | Add-Content $checkpoint -Encoding utf8
