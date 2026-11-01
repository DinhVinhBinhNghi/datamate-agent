DataMate Chat 3 - Group 1 patch

Contents:
- src\datamate\load_business.py
- src\datamate\__init__.py
- configs\businesses\train\biz_129.json
- install.ps1

Install from PowerShell after extracting this ZIP:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Then run from D:\ZALO:

  Set-Location D:\ZALO
  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m datamate.load_business --split train --business-id biz_129

Expected pilot facts:
- business_id: biz_129
- source: data/biz_129/don_hang.csv
- row_count: 38499
- order_key_null_count: 0
- order_key_duplicate_count: 0

This patch does not modify raw train/public_test data.
