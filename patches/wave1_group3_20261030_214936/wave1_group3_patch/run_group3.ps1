param([string]$ProjectRoot = 'D:\ZALO')

$ErrorActionPreference = 'Stop'
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { throw "Python not found: $Python" }
$env:PYTHONPATH = Join-Path $ProjectRoot 'src'
$AuditDir = Join-Path $ProjectRoot 'artifacts\audits'
$RunId = 'wave1_group3_' + (Get-Date -Format 'yyyyMMdd_HHmmss')
$OutputDir = Join-Path $ProjectRoot ("artifacts\eval\" + $RunId)
New-Item -ItemType Directory -Force -Path $AuditDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$Started = Get-Date

$PytestLog = Join-Path $OutputDir 'pytest.txt'
$PytestOutput = & $Python -m pytest `
    (Join-Path $ProjectRoot 'tests\planner') `
    (Join-Path $ProjectRoot 'tests\pipeline') -q 2>&1
$PytestExit = $LASTEXITCODE
$PytestOutput | Set-Content -LiteralPath $PytestLog -Encoding UTF8
$PytestOutput | Out-Host
if ($PytestExit -ne 0) { throw 'Group 3 tests failed; rollback before Group 4.' }

$ConsoleLog = Join-Path $OutputDir 'validation_console.txt'
$ValidationConsole = & $Python -m datamate.wave1_group3_validate `
    --project-root $ProjectRoot --output-dir $OutputDir 2>&1
$ValidationExit = $LASTEXITCODE
$ValidationConsole | Set-Content -LiteralPath $ConsoleLog -Encoding UTF8
$ReportPath = Join-Path $OutputDir 'wave1_group3_train_validation.json'
if ($ValidationExit -ne 0) {
    $ValidationConsole | Out-Host
    throw 'Exact train validation failed; public remains disabled. Roll back or inspect the report.'
}
if (-not (Test-Path -LiteralPath $ReportPath)) { throw "Missing validation report: $ReportPath" }
$Report = Get-Content -LiteralPath $ReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $Report.accepted) { throw 'Group 3 report was not accepted.' }
if (-not $Report.ground_truth_checked) { throw 'Safety failure: train ground truth was not checked.' }
if ($Report.overall.wrong -ne 0 -or $Report.overall.abstain -ne 0) {
    throw 'Safety failure: targeted train revenue has wrong or abstain outcomes.'
}
if ($Report.false_positive_answers_outside_target.Count -ne 0) {
    throw 'Safety failure: a non-target train question was answered.'
}
if ($Report.public_dev_002.revenue_enabled -or -not $Report.public_dev_002.all_eight_still_abstain) {
    throw 'Safety failure: public direct revenue must remain disabled in Group 3.'
}

$Businesses = foreach ($BusinessId in @('biz_102', 'biz_103', 'biz_104')) {
    $Item = $Report.per_business.$BusinessId
    [pscustomobject]@{
        business_id = $BusinessId
        total = $Item.total
        correct = $Item.correct
        wrong = $Item.wrong
        abstain = $Item.abstain
        score = $Item.score
        error_layers = $Item.error_layers
        runtime_seconds = $Item.wall_seconds
    }
}
$Summary = [ordered]@{
    passed = $true
    run_id = $RunId
    ground_truth_checked = $true
    scope = $Report.scope
    businesses = @($Businesses)
    overall = $Report.overall
    false_positive_answers_outside_target = $Report.false_positive_answers_outside_target.Count
    public_dev_002 = [ordered]@{
        direct_revenue_inventory = $Report.public_dev_002.direct_revenue_inventory
        revenue_enabled = $Report.public_dev_002.revenue_enabled
        all_eight_still_abstain = $Report.public_dev_002.all_eight_still_abstain
        existing_answer_count = $Report.baseline_regression.public_dev_002_answers
        accuracy = $null
    }
    baseline_behavior = [ordered]@{
        train_biz_129_correct = $Report.baseline_regression.train_biz_129.correct
        train_biz_129_wrong = $Report.baseline_regression.train_biz_129.wrong
        accepted = $Report.baseline_regression.accepted
    }
    artifacts = $Report.artifacts
    pytest_log = $PytestLog
    validation_console = $ConsoleLog
    rollback_command = "powershell -ExecutionPolicy Bypass -File `"<EXTRACTED_PATCH>\rollback.ps1`" -ProjectRoot `"$ProjectRoot`""
    elapsed_seconds = [math]::Round(((Get-Date) - $Started).TotalSeconds, 3)
    note = 'Train ground truth only. Public accuracy is unknown and public revenue remains disabled.'
}
$SummaryPath = Join-Path $AuditDir 'wave1_group3_summary.json'
$Summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SummaryPath -Encoding UTF8
Set-Content -LiteralPath (Join-Path $AuditDir 'wave1_group3_last_output.txt') -Value $OutputDir -Encoding UTF8
$Summary | ConvertTo-Json -Depth 8
