DataMate Chat 4 - Group 2 (time + status predicates)

Install from PowerShell after extracting:
  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_time_status.py

The calendar fixture resolves train/calendar.csv relative to the project root
(D:\ZALO\train\calendar.csv). No raw source is modified.
