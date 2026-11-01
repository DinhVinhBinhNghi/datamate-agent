DataMate Wave 1 - Group 1 archetype audit and train configs

Changes:
- generic xlsx_sheets reader for one workbook split across monthly sheets;
- train configs for biz_102, biz_103 and biz_104;
- semantic audit for those businesses plus public dev_002;
- dev_002 receives product/line-amount metadata only; revenue_enabled remains false;
- two focused tests for sheet loading and VND parsing.

Verified local audit facts:
- biz_102: 86,029 lines, 34,165 orders, 18 sheets, 2025-01-01..2026-06-16;
- biz_103: 45,534 lines, 18,133 orders, 16 sheets, 2025-04-01..2026-07-09;
- biz_104: 62,451 lines, 39,006 orders, 443 structural rows excluded;
- dev_002: 84,146 lines, 53,164 orders, 17 files, 946 structural rows excluded;
- zero invalid dates/amounts, cross-fragment orders, order conflicts or exact export duplicates.

The audit checks README semantics and confirms Tổng tiền is a line amount after discount.
It does not calculate revenue and does not enable any new public answer.
