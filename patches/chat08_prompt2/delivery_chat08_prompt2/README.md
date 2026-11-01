# DataMate Chat 08 Prompt 2 patch

This package adds a fail-closed capability expansion for the verified monthly Excel sales-line archetype. It never edits raw train/public data and contains no leaderboard submission action.

## Windows usage

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install_chat08.ps1 -ProjectRoot D:\ZALO
.\verify_chat08.ps1 -ProjectRoot D:\ZALO
.\run_chat08.ps1 -ProjectRoot D:\ZALO
```

To resume an interrupted run, reuse the printed run ID:

```powershell
.\run_chat08.ps1 -ProjectRoot D:\ZALO -RunId chat08_expansion_YYYYMMDD_HHMMSS -Resume
```

The installer verifies the frozen baseline and Candidate B hashes, backs up every overwritten file under `artifacts\backups`, then copies only the payload. The run script evaluates all 3,000 train questions before creating controlled Candidate-B children. Candidate E is intentionally blocked unless its product families pass exact development and holdout gates.

`measured_reference` records the Linux audit run and is not installed into D:\ZALO. Candidate values are included only as reproducibility evidence; public accuracy is unknown.
