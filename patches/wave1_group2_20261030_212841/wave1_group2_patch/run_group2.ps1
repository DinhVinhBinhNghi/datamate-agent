param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$AuditDir = Join-Path $ProjectRoot 'artifacts\audits'
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null
$Started = Get-Date

$PytestLog = Join-Path $AuditDir 'wave1_group2_pytest.txt'
$PytestOutput = & $Python -m pytest `
    (Join-Path $ProjectRoot 'tests\planner') `
    (Join-Path $ProjectRoot 'tests\pipeline') -q 2>&1
$PytestExit = $LASTEXITCODE
$PytestOutput | Set-Content -LiteralPath $PytestLog -Encoding UTF8
$PytestOutput | Out-Host
if ($PytestExit -ne 0) { throw 'Group 2 tests failed; stop before Group 3.' }

$BehaviorReport = Join-Path $AuditDir 'wave1_group2_baseline_behavior.json'
$BehaviorConsole = & $Python -m datamate.chat07_group2_check `
    --project-root $ProjectRoot --output $BehaviorReport 2>&1
$BehaviorExit = $LASTEXITCODE
$BehaviorConsole | Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group2_baseline_behavior_console.txt') -Encoding UTF8
if ($BehaviorExit -ne 0) { throw 'Baseline behavior changed; rollback Group 2.' }
$Behavior = Get-Content -LiteralPath $BehaviorReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Behavior.accepted) { throw 'Baseline behavior report was not accepted.' }

$RevenueReport = Join-Path $AuditDir 'wave1_group2_revenue_smoke.json'
$RevenueConsole = & $Python -m datamate.wave1_group2_check `
    --project-root $ProjectRoot --output $RevenueReport 2>&1
$RevenueExit = $LASTEXITCODE
$RevenueConsole | Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group2_revenue_smoke_console.txt') -Encoding UTF8
if ($RevenueExit -ne 0) { throw 'Real-data revenue invariants failed; rollback Group 2.' }
$Revenue = Get-Content -LiteralPath $RevenueReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Revenue.passed) { throw 'Group 2 revenue report did not pass.' }
if (-not $Revenue.public_fail_closed -or $Revenue.public_dev_002_revenue_enabled) {
    throw 'Safety failure: public dev_002 revenue must remain disabled.'
}

$Businesses = foreach ($Item in $Revenue.businesses) {
    [pscustomobject]@{
        business_id = $Item.business_id
        period = $Item.period
        result = $Item.result
        rows_in_period = $Item.evidence.rows_in_period_all_statuses
        eligible_rows = $Item.evidence.eligible_rows_after_status_filter
        orders_in_period = $Item.evidence.distinct_orders_in_period_all_statuses
        eligible_orders = $Item.evidence.eligible_distinct_orders
        excluded_statuses = $Item.evidence.excluded_statuses
        evidence_total_matches = $Item.checks.total_matches_answer
        runtime_seconds = $Item.runtime_seconds
        ground_truth_checked = $Item.ground_truth_checked
        passed = $Item.passed
    }
}
$Summary = [ordered]@{
    passed = $true
    public_dev_002_revenue_enabled = $false
    public_fail_closed = $Revenue.public_fail_closed
    ground_truth_checked = $false
    baseline_behavior = [ordered]@{
        train_biz_129_correct = $Behavior.train_biz_129.correct
        train_biz_129_wrong = $Behavior.train_biz_129.wrong
        public_dev_002_answers = $Behavior.public_dev_002_smoke.answers
        accepted = $Behavior.accepted
    }
    businesses = @($Businesses)
    revenue_report = $RevenueReport
    pytest_log = $PytestLog
    elapsed_seconds = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
    note = 'Invariant smoke only. Exact ground-truth validation is Group 3.'
}
$SummaryPath = Join-Path $AuditDir 'wave1_group2_summary.json'
$Summary | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
$Summary | ConvertTo-Json -Depth 7
