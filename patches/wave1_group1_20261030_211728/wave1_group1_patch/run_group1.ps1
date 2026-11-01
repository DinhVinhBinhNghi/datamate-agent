param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$AuditDir = Join-Path $ProjectRoot 'artifacts\audits'
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null
$Started = Get-Date

$PytestLog = Join-Path $AuditDir 'wave1_group1_pytest.txt'
$PytestOutput = & $Python -m pytest `
    (Join-Path $ProjectRoot 'tests\planner') `
    (Join-Path $ProjectRoot 'tests\pipeline') -q 2>&1
$PytestExit = $LASTEXITCODE
$PytestOutput | Set-Content -LiteralPath $PytestLog -Encoding UTF8
$PytestOutput | Out-Host
if ($PytestExit -ne 0) { throw 'Regression tests failed; stop before Group 2.' }

$BehaviorReport = Join-Path $AuditDir 'wave1_group1_baseline_behavior.json'
$BehaviorConsole = & $Python -m datamate.chat07_group2_check `
    --project-root $ProjectRoot --output $BehaviorReport 2>&1
$BehaviorExit = $LASTEXITCODE
$BehaviorConsole | Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group1_baseline_behavior_console.txt') -Encoding UTF8
if ($BehaviorExit -ne 0) { throw 'Baseline behavior changed; stop and rollback Group 1.' }
$Behavior = Get-Content -LiteralPath $BehaviorReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Behavior.accepted) { throw 'Baseline behavior report was not accepted.' }

$AuditReport = Join-Path $AuditDir 'wave1_group1_archetype_audit.json'
$AuditConsole = & $Python -m datamate.audit_monthly_sales `
    --project-root $ProjectRoot `
    --business train/biz_102 `
    --business train/biz_103 `
    --business train/biz_104 `
    --business public_test/dev_002 `
    --output $AuditReport 2>&1
$AuditExit = $LASTEXITCODE
$AuditConsole | Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group1_archetype_audit_console.txt') -Encoding UTF8
if ($AuditExit -ne 0) { throw 'Archetype audit failed; stop before Group 2.' }
$Audit = Get-Content -LiteralPath $AuditReport -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Audit.passed) { throw 'Archetype audit did not pass.' }
if ($Audit.public_revenue_enabled) { throw 'Safety failure: public revenue must remain disabled in Group 1.' }

$Businesses = foreach ($Report in $Audit.businesses) {
    [pscustomobject]@{
        business_id = $Report.business_id
        format = $Report.layout.format
        fragments = $Report.metrics.source_fragment_count
        raw_rows = $Report.metrics.row_count_before_filter
        sales_lines = $Report.metrics.row_count_after_structural_filter
        structural_rows = $Report.metrics.structural_rows_excluded
        distinct_orders = $Report.metrics.distinct_orders
        date_start = $Report.metrics.date_start
        date_end = $Report.metrics.date_end
        cross_fragment_orders = $Report.metrics.cross_fragment_order_ids
        invalid_dates = $Report.metrics.invalid_dates
        invalid_amounts = $Report.metrics.invalid_line_amounts
        duplicate_export_rows = $Report.metrics.duplicate_export_rows_extra
        repeated_order_total_detected = $Report.line_amount_evidence.systematic_repeated_order_total_detected
        passed = $Report.passed
    }
}
$Summary = [ordered]@{
    passed = $true
    public_revenue_enabled = $false
    baseline_behavior = [ordered]@{
        train_biz_129_correct = $Behavior.train_biz_129.correct
        train_biz_129_wrong = $Behavior.train_biz_129.wrong
        public_dev_002_answers = $Behavior.public_dev_002_smoke.answers
        accepted = $Behavior.accepted
    }
    businesses = @($Businesses)
    audit_report = $AuditReport
    pytest_log = $PytestLog
    elapsed_seconds = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
}
$SummaryPath = Join-Path $AuditDir 'wave1_group1_summary.json'
$Summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
$Summary | ConvertTo-Json -Depth 6
