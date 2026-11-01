DataMate Chat 3 - Group 4 measurement patch

This patch only adds direct-loader profiling. It does not create a cache.

Install after extracting:

  Set-ExecutionPolicy -Scope Process Bypass
  .\install.ps1 -ProjectRoot D:\ZALO

Run from D:\ZALO:

  $env:PYTHONPATH = 'D:\ZALO\src'
  .\.venv\Scripts\python.exe -m datamate.profile_runtime --repeats 3

Output:
- artifacts\loader\runtime_profile.json

The first load is process-first, not a guaranteed physical cold-disk read.
Memory is measured separately using tracemalloc so it does not distort timing.
