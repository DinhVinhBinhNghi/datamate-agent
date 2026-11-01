DataMate Wave 1 - Group 4 guarded public Candidate B

Precondition: accepted Group 3 source/config and the immutable baseline submission
chat07_public_20261030_181131 with SHA-256
c8c57a2cca00047099c293c5ba642d864d9b706132891bb43858cfc605cf7ea6.

This patch enables generic direct revenue for public dev_002 after the 29/29 exact
train validation. Planner scope is limited to one shop-wide revenue total for today,
yesterday, or an explicit month. Growth, average order, max day, product, customer,
ranking and multi-period questions remain unsupported.

run_group4.ps1 performs tests, repeats train regression, executes all 1,000 public
questions, validates UTF-8/IDs/types/evidence and compares every row with the frozen
baseline. Acceptance requires exactly eight abstain-to-integer-number changes, 18
total answered rows and zero unexpected changes. Only then is submission_<run_id>.jsonl
created. It never submits automatically and never overwrites the baseline.

Local reproduction before packaging passed: train 29/29; public 18 answered;
type counts abstain=982, number=15, percent=3; exactly eight expected changes;
no revenue evidence errors. Public accuracy is unknown.
