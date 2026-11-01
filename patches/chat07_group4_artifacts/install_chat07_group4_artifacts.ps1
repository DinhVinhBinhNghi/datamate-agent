param([string]$ProjectRoot = 'D:\ZALO')
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backup = Join-Path $ProjectRoot "artifacts\rollback\chat07_group4_$stamp"
$logDir = Join-Path $ProjectRoot 'artifacts\leaderboard'
$submissionDir = Join-Path $ProjectRoot 'artifacts\submissions'
$handoffDir = Join-Path $ProjectRoot 'handoffs'
New-Item -ItemType Directory -Force -Path $logDir,$submissionDir,$handoffDir | Out-Null

$incomingLog = Import-Csv -LiteralPath (Join-Path $Here 'submission_log.csv')
$targetLog = Join-Path $logDir 'submission_log.csv'
if (Test-Path -LiteralPath $targetLog) {
    $existing = Import-Csv -LiteralPath $targetLog
    if ($existing.run_id -contains 'chat07_public_20261030_181131') {
        Write-Host 'Log entry already exists; keeping current log.'
    } else {
        New-Item -ItemType Directory -Force -Path $backup | Out-Null
        Copy-Item -LiteralPath $targetLog -Destination $backup
        $incomingLog | Export-Csv -LiteralPath $targetLog -NoTypeInformation -Append -Encoding UTF8
    }
} else {
    Copy-Item -LiteralPath (Join-Path $Here 'submission_log.csv') -Destination $targetLog
}

$reviewName = 'submission_validation_chat07_public_20261030_181131_independent_review.json'
$reviewTarget = Join-Path $submissionDir $reviewName
if (-not (Test-Path -LiteralPath $reviewTarget)) {
    Copy-Item -LiteralPath (Join-Path $Here $reviewName) -Destination $reviewTarget
}
$handoffTarget = Join-Path $handoffDir 'chat07_handoff.md'
if (Test-Path -LiteralPath $handoffTarget) {
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Copy-Item -LiteralPath $handoffTarget -Destination $backup
}
Copy-Item -LiteralPath (Join-Path $Here 'chat07_handoff.md') -Destination $handoffTarget -Force
Write-Host "LOG:      $targetLog"
Write-Host "REVIEW:   $reviewTarget"
Write-Host "HANDOFF:  $handoffTarget"
if (Test-Path -LiteralPath $backup) { Write-Host "BACKUP:   $backup" }
