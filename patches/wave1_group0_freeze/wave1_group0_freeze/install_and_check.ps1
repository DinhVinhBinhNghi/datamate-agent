param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$ExpectedRunId = 'chat07_public_20261030_181131'
$ExpectedSha256 = 'c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6'
$ExpectedScore = '0.01'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Candidate = Join-Path $ProjectRoot "artifacts\submissions\submission_$ExpectedRunId.jsonl"
$LogPath = Join-Path $ProjectRoot 'artifacts\leaderboard\submission_log.csv'
$HandoffPath = Join-Path $ProjectRoot 'handoffs\chat07_handoff.md'
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Snapshot = Join-Path $ProjectRoot "artifacts\snapshots\wave1_prechange_$Stamp"
$BaselineDir = Join-Path $ProjectRoot 'artifacts\baselines\chat07_public_20261030_181131'

if (-not (Test-Path -LiteralPath $Python)) { throw "Không tìm thấy Python: $Python" }
if (-not (Test-Path -LiteralPath $Candidate)) { throw "Không tìm thấy baseline candidate: $Candidate" }
if (-not (Test-Path -LiteralPath $LogPath)) { throw "Không tìm thấy submission log: $LogPath" }
if (-not (Test-Path -LiteralPath $HandoffPath)) { throw "Không tìm thấy Chat 7 handoff: $HandoffPath" }

New-Item -ItemType Directory -Force -Path $Snapshot,$BaselineDir | Out-Null
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'

# Verify the candidate before creating or editing any metadata.
$VerifyReport = Join-Path $Snapshot 'baseline_validation.json'
& $Python (Join-Path $Here 'verify_baseline.py') `
    --project-root $ProjectRoot `
    --candidate $Candidate `
    --expected-sha256 $ExpectedSha256 `
    --output $VerifyReport
if ($LASTEXITCODE -ne 0) { throw 'Baseline candidate verification failed.' }

function Copy-SnapshotTree([string]$RelativePath) {
    $Source = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Source)) { throw "Missing snapshot source: $Source" }
    $Target = Join-Path $Snapshot $RelativePath
    Get-ChildItem -LiteralPath $Source -Recurse -File | Where-Object {
        $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
    } | ForEach-Object {
        $RelativeFile = $_.FullName.Substring($Source.Length).TrimStart('\')
        $TargetFile = Join-Path $Target $RelativeFile
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $TargetFile) | Out-Null
        Copy-Item -LiteralPath $_.FullName -Destination $TargetFile -Force
    }
}

# This is the recoverable source/config/test state before Wave 1 code changes.
Copy-SnapshotTree 'src'
Copy-SnapshotTree 'configs'
Copy-SnapshotTree 'tests'
New-Item -ItemType Directory -Force -Path (Join-Path $Snapshot 'metadata') | Out-Null
Copy-Item -LiteralPath $LogPath -Destination (Join-Path $Snapshot 'metadata\submission_log.csv')
Copy-Item -LiteralPath $HandoffPath -Destination (Join-Path $Snapshot 'metadata\chat07_handoff.md')

$FrozenCandidate = Join-Path $BaselineDir "submission_$ExpectedRunId.jsonl"
if (Test-Path -LiteralPath $FrozenCandidate) {
    $FrozenHash = (Get-FileHash -LiteralPath $FrozenCandidate -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($FrozenHash -ne $ExpectedSha256) { throw "Existing frozen baseline has unexpected SHA-256: $FrozenHash" }
} else {
    Copy-Item -LiteralPath $Candidate -Destination $FrozenCandidate
}

$ManifestTargets = @(
    (Join-Path $ProjectRoot 'src'),
    (Join-Path $ProjectRoot 'configs'),
    (Join-Path $ProjectRoot 'tests'),
    (Join-Path $ProjectRoot 'train\questions.jsonl'),
    (Join-Path $ProjectRoot 'train\answers.jsonl'),
    (Join-Path $ProjectRoot 'train\rulebook.md'),
    (Join-Path $ProjectRoot 'public_test\questions.jsonl'),
    (Join-Path $ProjectRoot 'public_test\rulebook.md'),
    (Join-Path $ProjectRoot 'train\data\biz_102'),
    (Join-Path $ProjectRoot 'train\data\biz_103'),
    (Join-Path $ProjectRoot 'train\data\biz_104'),
    (Join-Path $ProjectRoot 'public_test\data\dev_002'),
    $Candidate
)
$ManifestFiles = foreach ($Target in $ManifestTargets) {
    if (Test-Path -LiteralPath $Target -PathType Container) {
        Get-ChildItem -LiteralPath $Target -Recurse -File
    } elseif (Test-Path -LiteralPath $Target -PathType Leaf) {
        Get-Item -LiteralPath $Target
    } else {
        throw "Missing manifest target: $Target"
    }
}
$ManifestRows = $ManifestFiles | Where-Object {
    $_.FullName -notmatch '[\\/]__pycache__[\\/]' -and $_.Extension -ne '.pyc'
} | Sort-Object FullName -Unique | ForEach-Object {
    [pscustomobject]@{
        path = $_.FullName.Substring($ProjectRoot.Length).TrimStart('\')
        size_bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
$Manifest = [ordered]@{
    snapshot_id = "wave1_prechange_$Stamp"
    created_at_local = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssK')
    baseline_run_id = $ExpectedRunId
    baseline_submission_sha256 = $ExpectedSha256
    leaderboard_score = 0.01
    leaderboard_score_source = 'user_reported'
    scope = 'pre-Wave-1 source/config/tests plus relevant data hashes'
    files = @($ManifestRows)
}
$Manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Snapshot 'freeze_manifest.json') -Encoding UTF8

# Regression must pass before the leaderboard log or handoff is changed.
$RegressionLog = Join-Path $Snapshot 'pytest_regression.txt'
& $Python -m pytest (Join-Path $ProjectRoot 'tests\planner') (Join-Path $ProjectRoot 'tests\pipeline') -q 2>&1 | Tee-Object -FilePath $RegressionLog
if ($LASTEXITCODE -ne 0) { throw 'Current pytest regression failed; metadata was not updated.' }

$BehaviorReport = Join-Path $Snapshot 'behavior_regression.json'
& $Python -m datamate.chat07_group2_check --project-root $ProjectRoot --output $BehaviorReport
if ($LASTEXITCODE -ne 0) { throw 'Baseline behavior regression failed; metadata was not updated.' }

# Update exactly the existing baseline row. Slot remains blank because it was not reported.
$Rows = @(Import-Csv -LiteralPath $LogPath)
$Match = @($Rows | Where-Object { $_.run_id -eq $ExpectedRunId })
if ($Match.Count -ne 1) { throw "Expected exactly one submission log row for $ExpectedRunId; found $($Match.Count)." }
$Match[0].leaderboard_score = $ExpectedScore
$ScoreNote = 'Submitted manually; leaderboard score 0.01 reported by user on 2026-10-30. Score is aggregate only and is not a per-question label.'
if ($Match[0].notes -notlike '*leaderboard score 0.01*') {
    $Match[0].notes = ($Match[0].notes.TrimEnd() + ' ' + $ScoreNote).Trim()
}
$Rows | Export-Csv -LiteralPath $LogPath -NoTypeInformation -Encoding UTF8

$Handoff = Get-Content -LiteralPath $HandoffPath -Raw -Encoding UTF8
$Handoff = [regex]::Replace(
    $Handoff,
    '(?m)^- Best leaderboard run:.*$',
    "- Best leaderboard run: ``$ExpectedRunId``; user-reported leaderboard score ``0.01``. Aggregate score only; no per-question labels inferred."
)
$Handoff = [regex]::Replace(
    $Handoff,
    '(?m)^- Submission log:.*$',
    "- Submission log: ``artifacts/leaderboard/submission_log.csv``; baseline was submitted manually and score ``0.01`` was recorded; slot remains blank because it was not reported."
)
$Handoff | Set-Content -LiteralPath $HandoffPath -Encoding UTF8

Set-Content -LiteralPath (Join-Path $ProjectRoot 'artifacts\snapshots\wave1_prechange_last.txt') -Value $Snapshot -Encoding UTF8
$Summary = [ordered]@{
    passed = $true
    baseline_run_id = $ExpectedRunId
    baseline_sha256 = $ExpectedSha256
    leaderboard_score = 0.01
    candidate_unchanged = $true
    snapshot = $Snapshot
    manifest = (Join-Path $Snapshot 'freeze_manifest.json')
    validator = $VerifyReport
    behavior_regression = $BehaviorReport
    pytest_log = $RegressionLog
    rollback_command = "powershell -ExecutionPolicy Bypass -File `"$Here\rollback.ps1`" -ProjectRoot `"$ProjectRoot`""
}
$Summary | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Snapshot 'group0_summary.json') -Encoding UTF8
$Summary | ConvertTo-Json -Depth 4
