Chat 07 Group 3 — reproducible public full run and candidate packaging.

One command freezes code/config, runs or resumes all 1,000 public questions,
validates exact IDs and official shapes, and writes:
  artifacts/submissions/submission_<run_id>.jsonl
  artifacts/submissions/submission_validation_<run_id>.json
  artifacts/runs/<run_id>/public_run_report_<run_id>.md
  artifacts/runs/<run_id>/freeze_manifest.json

It does not submit to the leaderboard and never reports public accuracy.
Rollback, if installation tests fail:
  powershell -ExecutionPolicy Bypass -File .\rollback.ps1
