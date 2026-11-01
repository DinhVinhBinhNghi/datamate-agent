DataMate Wave 1 - Group 2 generic direct revenue

Adds a shared revenue function for the verified monthly Excel sales-line archetype.
The function receives an already-resolved Period, uses order date, sums integer VND
line amounts, excludes the whole cancelled/returned order, includes in-delivery orders,
deduplicates exact export duplicates and fails closed on source/grain conflicts.

Evidence contains source files/sheets, requested/effective periods, row counts before
and after every filter, distinct orders, excluded statuses and final total.

Train configs biz_102/biz_103/biz_104 enable this direct function. Public dev_002 stays
disabled. No planner, executor or public-question capability is changed in Group 2.

The real-data smoke uses May 2025 and checks accounting invariants only. Its totals are
not treated as labels; exact train-answer scoring belongs to Group 3.
