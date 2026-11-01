param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$BaselineRun = 'chat07_public_20261030_181131'
$BaselineSha = 'c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6'
$CandidateRun = 'wave1_public_revenue_20261030_220018'
$CandidateSha = '0eb7eb9f730bf8f0cbafb8dc3db5fe73b4f75bef99086dfcd5e21591ccf8c66a'
$BaselinePath = Join-Path $ProjectRoot "artifacts\submissions\submission_$BaselineRun.jsonl"
$CandidatePath = Join-Path $ProjectRoot "artifacts\submissions\submission_$CandidateRun.jsonl"
$LogPath = Join-Path $ProjectRoot 'artifacts\leaderboard\submission_log.csv'
$HandoffPath = Join-Path $ProjectRoot 'handoffs\chat07_handoff.md'

foreach ($Check in @(@($BaselinePath, $BaselineSha), @($CandidatePath, $CandidateSha))) {
    if (-not (Test-Path -LiteralPath $Check[0])) { throw "Missing submission: $($Check[0])" }
    $Actual = (Get-FileHash -LiteralPath $Check[0] -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($Actual -ne $Check[1]) { throw "SHA-256 mismatch: $($Check[0])" }
}
if (-not (Test-Path -LiteralPath $LogPath)) { throw "Submission log missing: $LogPath" }

$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $ProjectRoot "artifacts\rollback\chat07_wave1_closeout_$Stamp"
New-Item -ItemType Directory -Force -Path (Join-Path $Backup 'artifacts\leaderboard') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $Backup 'handoffs') | Out-Null
Copy-Item -LiteralPath $LogPath -Destination (Join-Path $Backup 'artifacts\leaderboard\submission_log.csv') -Force
if (Test-Path -LiteralPath $HandoffPath) {
    Copy-Item -LiteralPath $HandoffPath -Destination (Join-Path $Backup 'handoffs\chat07_handoff.md') -Force
}

$Rows = @(Import-Csv -LiteralPath $LogPath)
$Required = @('timestamp','slot','run_id','parent_run','change','local_validation_metrics','public_coverage','leaderboard_score','notes')
if ($Rows.Count -lt 1 -or @($Required | Where-Object { $_ -notin $Rows[0].PSObject.Properties.Name }).Count) {
    throw 'submission_log.csv schema does not match the accepted Chat 7 schema.'
}
$Baseline = @($Rows | Where-Object { $_.run_id -eq $BaselineRun })
if ($Baseline.Count -ne 1) { throw "Expected one baseline row; found $($Baseline.Count)." }
$Baseline[0].leaderboard_score = '0.01'
if ($Baseline[0].notes -notlike '*user-reported leaderboard score 0.01*') {
    $Baseline[0].notes = ($Baseline[0].notes.TrimEnd() + ' Submitted manually; user-reported leaderboard score 0.01; aggregate signal only.').Trim()
}
$Candidate = @($Rows | Where-Object { $_.run_id -eq $CandidateRun })
if ($Candidate.Count -gt 1) { throw "Duplicate Candidate B log rows: $($Candidate.Count)." }
if ($Candidate.Count -eq 0) {
    $Rows += [pscustomobject][ordered]@{
        timestamp = '2026-10-30T22:00:18+07:00 (run created; submission timestamp not supplied)'
        slot = ''
        run_id = $CandidateRun
        parent_run = $BaselineRun
        change = 'Wave 1 only: add 8 direct shop-wide revenue answers for dev_002; preserve baseline 10 answers'
        local_validation_metrics = '90 passed + 40 subtests; train direct revenue 29/29 correct, 0 wrong/abstain; 0 false positives; biz_129 7 correct/0 wrong'
        public_coverage = '18/1000 answered (15 number, 3 percent); 982 abstain; exactly 8 expected changes; 0 evidence errors'
        leaderboard_score = '0.018'
        notes = "Submitted manually; user-reported leaderboard score 0.018. SHA256 $CandidateSha. Delta +0.008 vs baseline; aggregate signal only, not per-question labels. Submission timestamp/slot not reported."
    }
} else {
    $Candidate[0].leaderboard_score = '0.018'
    $Candidate[0].notes = "Submitted manually; user-reported leaderboard score 0.018. SHA256 $CandidateSha. Delta +0.008 vs baseline; aggregate signal only, not per-question labels. Submission timestamp/slot not reported."
}
$Rows | Export-Csv -LiteralPath $LogPath -NoTypeInformation -Encoding UTF8
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $HandoffPath) | Out-Null
Copy-Item -LiteralPath (Join-Path $Here 'handoffs\chat07_handoff.md') -Destination $HandoffPath -Force

$Summary = [ordered]@{
    passed = $true
    best_local_run = $CandidateRun
    best_leaderboard_run = $CandidateRun
    baseline_score = 0.01
    candidate_b_score = 0.018
    leaderboard_delta = 0.008
    submission_log = $LogPath
    handoff = $HandoffPath
    backup = $Backup
    timestamp_and_slot_complete = $false
}
$Summary | ConvertTo-Json -Depth 3
