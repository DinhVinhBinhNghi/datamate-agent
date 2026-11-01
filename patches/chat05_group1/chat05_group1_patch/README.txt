DataMate Chat 5 / Group 1 — incremental patch on top of the verified Chat 3/4 D:\ZALO project.
Extract ZIP to a temporary folder, then run its install.ps1 from PowerShell.
The installer copies only new planner files and tests; it does not touch train/public data, prior source, or oracle fixtures.
Requires the existing Chat 4 oracle executor and pandas. No model runtime needed.
Run from D:\ZALO with PYTHONPATH=src. The CLI appends actual Windows runs under artifacts\planner.
Current report describes a local Linux checkpoint; repeat the commands on Windows.
