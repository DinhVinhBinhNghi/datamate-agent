DataMate Wave 1 - Group 3 exact train validation

This patch enables the already-audited monthly Excel direct-revenue function only for
train businesses biz_102, biz_103 and biz_104. It adds a narrow classifier for one
shop-wide revenue total over one resolved period. Growth/comparison, average order,
ranking/threshold, entity-specific and multi-period questions fail closed.

The evaluator inventories all 357 questions from the three businesses, then runs the
full planner -> executor -> evidence gate -> formatter -> scorer path. Acceptance is
13/13, 6/6 and 10/10 exact train answers, no answered question outside the target,
and unchanged biz_129/dev_002 baseline behavior.

The same generic classifier sees eight direct-revenue questions in public dev_002,
but Group 3 deliberately leaves revenue_enabled=false and verifies all eight remain
abstain. Public accuracy is not estimated.

Local Linux reproduction before packaging: 29 correct, 0 wrong, 0 abstain; no false
positive answers; baseline biz_129 7 correct/0 wrong; public dev_002 still 10 answers.
Run run_group3.ps1 on D:\ZALO to reproduce using the Windows environment and data.
