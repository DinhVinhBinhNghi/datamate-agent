DataMate Chat 4 - Group 4 oracle executor and regression fixtures

Install after extracting:
  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_oracle_plan.py
  .\.venv\Scripts\python.exe -m datamate.execution.oracle_plan --plans artifacts\business\oracle_plans_train.jsonl --project-root . --data-root train --output artifacts\business\oracle_results.jsonl

Outputs:
- artifacts\business\oracle_results.jsonl
- artifacts\business\oracle_report.md

Allowlisted operations: resolve_period, revenue, order_count, cancel_rate.
Current development support: train ruleset, time resolver, biz_129 metrics only.
Public ruleset and other businesses return unsupported with explicit reason.
