# Ground truth reviewed v2

50 câu đã biết, cutoff 22/09/2026. Chủ dự án duyệt phương án rà có AI hỗ trợ
ngày 14/10/2026. Đây không phải tập held-out hoặc kết quả model.

- `cases.jsonl`: câu hỏi, đáp án, facet bắt buộc/bổ sung, evidence và điều kiện trạng thái.
- `REVIEWED.md`: bản đọc để duyệt/đối chiếu.
- `review_decisions.json`: lý do, thay đổi câu hỏi và hash trước/sau mỗi câu.
- `manifest.json`: phê duyệt, phiên bản và checksum đầu vào/artifact.

Giữ nguyên v1 cùng lịch sử/provenance; v2 tham chiếu v1 thay vì sao chép
model answer lịch sử vào gold mới. 9 câu sửa nhãn/nội dung, 7 câu tinh chỉnh;
34 câu giữ nội dung. Câu hỏi 007/013/033 được làm rõ; kết quả cũ của các câu
này không tương đương một lượt chạy mới.

Bốn nhãn abstain cũ 010/023/029/043 nay có căn cứ trả lời. Năm câu conditional
016/042/044/046/048 có tiêu chí riêng cho trả lời theo điều kiện, hỏi rõ và
trả lời một phần. Cho phép trạng thái không tự chứng minh nội dung đúng.
V2 có 45 publish và 5 conditional; chưa có câu thiếu nguồn thực sự, do đó
không dùng riêng bộ này đo đầy đủ khả năng từ chối. Dùng guard/development
hoặc bộ bổ sung được duyệt cho phép đo đó.

Facet `required=false` không nằm trong mẫu số completeness nhưng mọi thông
tin bổ sung model phát biểu vẫn phải đúng và có nguồn. Evidence trong các
nhóm thay thế có thể OR; `match=all` bên trong nhóm là AND. Ánh xạ leaf ID
qua `source_processed_ids`; đây chưa phải qrels phân cấp đầy đủ.

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
.venv/bin/python -m evaluation.core_runner prepare --suite reviewed --output outputs/evaluation/labels-v2-run/plan.json
```

Tạo plan/preflight mới trước khi chạy. `--suite legacy` vẫn dùng reviewed v1;
không ghi đè kết quả hoặc đổi nhãn của lượt đã hoàn thành.
