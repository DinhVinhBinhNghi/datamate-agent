DataMate Wave 1 - Group 0 freeze

This bundle verifies the immutable Chat 7 baseline, snapshots source/config/tests,
hashes relevant train/public data, runs pytest plus behavior regression, then records
the user-reported leaderboard score 0.01 in submission_log.csv and chat07_handoff.md.

It never edits the baseline submission JSONL.

Install/check:
powershell -ExecutionPolicy Bypass -File .\install_and_check.ps1 -ProjectRoot D:\ZALO

Rollback (only after a future Wave 1 change if needed):
powershell -ExecutionPolicy Bypass -File .\rollback.ps1 -ProjectRoot D:\ZALO
