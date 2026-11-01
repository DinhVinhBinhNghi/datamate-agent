Chat 07 Group 2 test-only hotfix.

Cause: the synthetic CONFIG fixture omitted path_glob required by the in-process cache signature.
Runtime code, public answers and production config are unchanged.

Install, then rerun:
  powershell -ExecutionPolicy Bypass -File .\install.ps1
  Set-Location D:\ZALO
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest tests\planner tests\pipeline -q
