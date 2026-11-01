Chat 07 Group 2 — public_test/dev_002 order and cancellation experiment.

Single cause changed: missing public adapter/config/gates for verified order-header metrics.
Enabled only: order_count, cancel_count, cancel_rate for dev_002.
Revenue, ranking, products, customers and every other public business remain fail-closed.
No public question ID or answer is embedded in runtime code.

Install from the extracted folder:
  powershell -ExecutionPolicy Bypass -File .\install.ps1

Then run the commands supplied in chat. Do not submit a file until Group 3 full-run validation.
Acceptance command after pytest:
  python -m datamate.chat07_group2_check --project-root D:\ZALO
Rollback if the Windows regression fails:
  powershell -ExecutionPolicy Bypass -File .\rollback.ps1
