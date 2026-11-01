DataMate Chat 3 - Group 4 targeted cache benchmark

Scope: train/biz_116/sales_lines only. The cache is derived and rebuildable.
Its key includes source SHA-256, config SHA-256, and loader version. Build uses
a temporary SQLite file followed by atomic replace under data\cache.

Install after extracting:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run benchmark from D:\ZALO:

  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m datamate.benchmark_cache --repeats 3

Then verify the cached loader:

  .\.venv\Scripts\python.exe -m datamate.load_business --split train --business-id biz_116 --use-cache

Output:
- artifacts\loader\cache_benchmark.json
- data\cache\train\biz_116\sales_lines\<cache-key>.sqlite

The benchmark asserts exact DataFrame round-trip equality, including dtypes.
