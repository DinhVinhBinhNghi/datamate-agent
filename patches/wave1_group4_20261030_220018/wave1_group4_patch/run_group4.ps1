param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$Baseline = Join-Path $ProjectRoot 'artifacts\submissions\submission_chat07_public_20261030_181131.jsonl'
$ExpectedBaselineHash = 'c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6'
if (-not (Test-Path -LiteralPath $Baseline)) { throw "Frozen baseline not found: $Baseline" }
$ActualBaselineHash = (Get-FileHash -LiteralPath $Baseline -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualBaselineHash -ne $ExpectedBaselineHash) { throw 'Frozen baseline SHA-256 mismatch.' }

$RunId = 'wave1_public_revenue_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$OutputDir = Join-Path $ProjectRoot ("artifacts\runs\" + $RunId)
$AuditDir = Join-Path $ProjectRoot 'artifacts\audits'
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null
$Started = Get-Date

$PytestLog = Join-Path $AuditDir ("wave1_group4_pytest_" + $RunId + '.txt')
$PytestOutput = & $Python -m pytest `
    (Join-Path $ProjectRoot 'tests\planner') `
    (Join-Path $ProjectRoot 'tests\pipeline') -q 2>&1
$PytestExit = $LASTEXITCODE
$PytestOutput | Set-Content -LiteralPath $PytestLog -Encoding UTF8
$PytestOutput | Out-Host
if ($PytestExit -ne 0) { throw 'Group 4 tests failed; do not create or submit Candidate B.' }

$ConsoleLog = Join-Path $AuditDir ("wave1_group4_console_" + $RunId + '.txt')
$Console = & $Python -m datamate.wave1_group4_public `
    --project-root $ProjectRoot --run-id $RunId --baseline $Baseline 2>&1
$RunExit = $LASTEXITCODE
$Console | Set-Content -LiteralPath $ConsoleLog -Encoding UTF8
$DiffReport = Join-Path $OutputDir ("public_diff_" + $RunId + '.json')
if ($RunExit -ne 0) {
    $Console | Out-Host
    throw 'Guarded public run failed. No validated submission was produced.'
}
if (-not (Test-Path -LiteralPath $DiffReport)) { throw "Missing public diff report: $DiffReport" }
$Report = Get-Content -LiteralPath $DiffReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Report.passed -or -not $Report.candidate.valid) { throw 'Candidate B was not accepted.' }
if (-not $Report.baseline.unchanged) { throw 'Baseline changed during Group 4.' }
if (-not $Report.train_regression.accepted) { throw 'Train regression failed.' }
if (-not $Report.diff.passed -or $Report.diff.actual_change_count -ne 8) { throw 'Public diff is not exactly eight expected rows.' }
if ($Report.candidate.answered_count -ne 18) { throw 'Candidate must answer exactly 18 questions.' }
if ($Report.revenue_evidence_errors.Count -ne 0) { throw 'Revenue evidence review failed.' }

$Submission = $Report.candidate.submission
if (-not (Test-Path -LiteralPath $Submission)) { throw "Submission not found: $Submission" }
$SubmissionHash = (Get-FileHash -LiteralPath $Submission -Algorithm SHA256).Hash.ToLowerInvariant()
if ($SubmissionHash -ne $Report.candidate.sha256) { throw 'Submission hash differs from validation report.' }
$BaselineHashAfter = (Get-FileHash -LiteralPath $Baseline -Algorithm SHA256).Hash.ToLowerInvariant()
if ($BaselineHashAfter -ne $ExpectedBaselineHash) { throw 'Baseline changed after public run.' }

$Reproduce = "`$env:PYTHONPATH='D:\ZALO\src'; .\.venv\Scripts\python.exe -m datamate.wave1_group4_public --project-root D:\ZALO --run-id $RunId --baseline `"$Baseline`""
$Summary = [ordered]@{
    passed = $true
    run_id = $RunId
    baseline = [ordered]@{
        run_id = $Report.baseline.run_id
        path = $Baseline
        sha256 = $ExpectedBaselineHash
        unchanged = $true
    }
    tests = [ordered]@{ passed = $true; log = $PytestLog }
    train_regression = [ordered]@{
        correct = $Report.train_regression.overall.correct
        wrong = $Report.train_regression.overall.wrong
        abstain = $Report.train_regression.overall.abstain
        false_positive_answers = $Report.train_regression.false_positive_answers_outside_target.Count
        biz_129_correct = $Report.train_regression.biz_129.correct
        biz_129_wrong = $Report.train_regression.biz_129.wrong
        accepted = $Report.train_regression.accepted
    }
    public = [ordered]@{
        question_count = 1000
        answered = $Report.candidate.answered_count
        abstain = $Report.candidate.type_counts.abstain
        number = $Report.candidate.type_counts.number
        percent = $Report.candidate.type_counts.percent
        revenue_additions = $Report.diff.actual_change_count
        unexpected_changes = $Report.diff.unexpected_changes.Count
        missing_expected_changes = $Report.diff.missing_expected_changes.Count
        evidence_errors = $Report.revenue_evidence_errors.Count
        accuracy = $null
    }
    submission = $Submission
    submission_sha256 = $SubmissionHash
    validation = $Report.candidate.validation
    public_diff_report = $DiffReport
    public_run_report = Join-Path $OutputDir ("public_run_report_" + $RunId + '.md')
    freeze_manifest = $Report.freeze_manifest
    console_log = $ConsoleLog
    reproduce_command = $Reproduce
    rollback_command = "powershell -ExecutionPolicy Bypass -File `"<EXTRACTED_PATCH>\rollback.ps1`" -ProjectRoot `"$ProjectRoot`""
    elapsed_seconds = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
    note = 'Candidate B is structurally/evidence validated only. Public accuracy remains unknown. Do not infer per-question correctness from leaderboard score.'
}
$SummaryPath = Join-Path $AuditDir 'wave1_group4_summary.json'
$Summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group4_last_run.txt') -Value $RunId -Encoding UTF8
$Summary | ConvertTo-Json -Depth 8
