# Chat 01 Handoff — DataMate

## Đã xác minh
- Python: 3.11.9 tại Python311.
- Ổ D còn khoảng 140.84 GB trên tổng 195.31 GB.
- Train: 3,000 questions, 3,000 answers, 30 business folders.
- Public: 1,000 questions, không có answers, 14 business folders.
- Tất cả JSONL đã parse thành công.
- Không có ID trùng, ID thiếu hoặc business folder thiếu.
- Không có as_of_date lỗi trong audit.
- Dữ liệu nằm đúng tại D:\ZALO\train và D:\ZALO\public_test.
- ZIP gốc không còn tìm thấy; SHA-256 ZIP chưa xác minh.

## Môi trường
- Kích hoạt: .\.venv\Scripts\Activate.ps1
- Python trực tiếp: .\.venv\Scripts\python.exe
- Dependencies: requirements.txt
- Lock: requirements-lock.txt
- Khi chạy mã src: $env:PYTHONPATH='D:\ZALO\src'

## Cây file đã tạo
- data\source\source_manifest.json
- data\cache\
- data\raw\
- artifacts\audit\contract_summary.json
- src\datamate\__init__.py
- src\datamate\contracts.py
- src\datamate\audit_questions.py
- src\datamate\validate_submission.py
- tests\test_contracts.py
- tests\fixtures\
- .gitignore

## Kiểm thử
- pytest: PASS toàn bộ.
- Validator fixture hợp lệ: PASS.
- Validator fixture sai: PASS, bắt number dạng chuỗi, percent/date/list sai và ID trùng.
- Audit structural: PASS.
- Output audit: artifacts\audit\contract_summary.json.

## Còn thiếu hoặc giới hạn
- Chưa có hash ZIP gốc.
- Chưa suy luận schema bảng nghiệp vụ.
- Chưa có official scorer hoặc normalize/tolerance.
- Chưa xây agent, planner hoặc loader nghiệp vụ.

## Đầu vào bắt buộc cho Chat 2
- Đọc handoff này.
- Đọc README/rulebook và dataset reference nếu có.
- Không giả định schema ngoài kết quả audit.
- Tiếp tục từ D:\ZALO, giữ dữ liệu gốc chỉ đọc.
