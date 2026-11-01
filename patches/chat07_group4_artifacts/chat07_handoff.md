# Chat 7 handoff

- Best local run: `chat07_group2_train_local_v2`; 3,000 train rows, 7 answered, 2,993 abstain; 7 correct, 0 wrong, local score 7. Biz129: 7/118 answered, 0 wrong, 111 abstain.
- Best leaderboard run: none known; no submission/score was reported.
- Current candidate: `chat07_public_20261030_181131`; file `artifacts/submissions/submission_chat07_public_20261030_181131.jsonl`; SHA-256 `c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6`.
- Reproduce from frozen project: `$env:PYTHONPATH='D:\ZALO\src'; .\.venv\Scripts\python.exe -m datamate.chat07_public_candidate --project-root D:\ZALO --run-id chat07_public_20261030_181131`.
- Windows public result: 1,000 rows; 990 abstain, 7 number, 3 percent; 10 answered (1%); 38.641s invocation; `valid=true`; public accuracy unknown.
- Attached candidate independently checked against public question IDs: 1,000/1,000 in exact order; no duplicates/missing/extra/errors; UTF-8, no BOM, final newline; SHA matches Windows run output.
- Test result from user: 43 passed, 40 subtests passed in 14.23s.
- Accepted: Group2 public dev002 order_count/cancel_count/cancel_rate adapter; Group3 frozen full-run packaging and validator. No rollback reported.
- Submission log: `artifacts/leaderboard/submission_log.csv`; candidate is marked prepared only; slot and leaderboard score blank because manual submission is pending.
- Known risks: no public gold labels; most public questions abstain. Freeze manifest hashes code/config/questions/rulebook/calendar, not raw public workbooks or README. Public run/report file was generated on the Windows project; only submission JSONL was attached here.
- Unsupported/backlog: other public businesses/families, public source-file hashing, broader business-rule coverage, improve safe coverage from measured train errors.
- Meeting: decide whether to manually submit this one validated candidate; after leaderboard result, record date/slot/score without inferring per-question correctness.
- Chat 8: proceed only after submission decision/result and reviewing current run artifacts, or if time remains to tackle a separately measured local error bucket.
