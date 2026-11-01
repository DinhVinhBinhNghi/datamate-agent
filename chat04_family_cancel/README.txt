DataMate Chat 4 - Cancel family (train/biz_129)

Install:
  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_cancel.py
  .\.venv\Scripts\python.exe -m datamate.business.cancel --business-id biz_129 --period "tháng 1/2025" --as-of-date 2025-01-31

Expected: 36 cancelled / 1880 all-status orders = 1.91%.
The 3 returned orders are in the denominator and are not cancellations.
Rule: train/rulebook.md §1. Raw data is read-only.
