DataMate Chat 3 - Group 3 patch

Adds the verified biz_123 orders-to-order-lines one-to-many JOIN helper,
cardinality diagnostics, header-total safety, tests, and deterministic smoke
pipeline. Includes all files from Groups 1 and 2.

Install after extracting:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:

  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_direct_readers.py tests\test_join_helper.py
  .\.venv\Scripts\python.exe -m datamate.smoke_pipeline --split train --business-id biz_123

Expected smoke facts:
- orders: 33630
- order_lines/joined rows: 64149
- unmatched keys: 0 on both sides
- row inflation vs orders: 1.907493309545049
- header total is summed from orders before JOIN: 3733287000

Generated files:
- artifacts\loader\smoke_result.json
- artifacts\loader\quality_report.json

Raw data is never written. SQLite is opened with mode=ro.
