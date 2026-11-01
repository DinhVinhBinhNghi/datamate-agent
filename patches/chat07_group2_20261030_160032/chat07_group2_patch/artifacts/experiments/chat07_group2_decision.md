# Chat 07 Group 2 decision

- Primary cause: public_test/dev_002 had verified order columns and rulebook semantics but no adapter/config/gate.
- Scope: order_count, cancel_count and cancel_rate only.
- Estimated affected inventory: 10 of 41 dev_002 public questions; this is coverage inventory, not accuracy.
- Safety: collapse product lines to unique order IDs only after normalized date/status consistency checks.
- Local result: train/biz_129 remains 7 correct, 0 wrong, 111 abstain (118 questions); full train remains 7 answers and 2,993 abstains.
- Targeted public smoke: 10 answers and 31 planner abstains across 41 dev_002 questions; no execution/gate/format failure; no public accuracy claimed.
- Runtime: targeted dev_002 smoke 11.799 seconds after in-process cache (local container run).
- Windows pytest and rerun are still required before accepting the change.
- Reject: any train regression, source-count mismatch, header conflict, missing provenance, or unexpected public family answer.
