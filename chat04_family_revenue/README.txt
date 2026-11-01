DataMate Chat 4 - Revenue family (train/biz_129)

Install after extracting:
  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_revenue.py
  .\.venv\Scripts\python.exe -m datamate.business.revenue --business-id biz_129 --period "tháng 1/2025" --as-of-date 2025-01-31

Expected oracle value: 955917000 VND.
Rules: train/rulebook.md §1; README: train/data/biz_129/README.md.
Raw data is read-only. Revenue sums detail-line totals after line discounts;
cancelled and returned orders are excluded; delivery status remains eligible.
