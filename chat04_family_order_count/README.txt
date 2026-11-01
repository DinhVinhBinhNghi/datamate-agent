DataMate Chat 4 - Order count family (train/biz_129)

Install:
  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_order_count.py
  .\.venv\Scripts\python.exe -m datamate.business.order_count --business-id biz_129 --period "tháng 1/2025" --as-of-date 2025-01-31

Expected: 1841 eligible orders; 1880 total orders in period.
Rules: train/rulebook.md §1; data description: train/data/biz_129/README.md.
