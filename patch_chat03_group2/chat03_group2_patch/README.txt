DataMate Chat 3 - Group 2 patch

This patch adds direct CSV, XLSX, and read-only SQLite readers, provenance,
two verified configs, and reader tests. It also includes the Group 1 files.

Install after extracting:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:

  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m pytest -q tests\test_direct_readers.py
  .\.venv\Scripts\python.exe -m datamate.load_business --split train --business-id biz_129
  .\.venv\Scripts\python.exe -m datamate.load_business --split train --business-id biz_116
  .\.venv\Scripts\python.exe -m datamate.load_business --split train --business-id biz_123

Observed direct-source checks:
- biz_129/orders CSV: 38499 rows, 0 null order keys, 0 duplicate order keys
- biz_116/sales_lines XLSX: 39889 rows, 0 null order keys, 21790 duplicate
  order keys expected because each row is a sales line
- biz_123/orders SQLite: 33630 rows, 0 null order keys, 0 duplicate order keys

Raw data is never written. SQLite is opened with mode=ro.
