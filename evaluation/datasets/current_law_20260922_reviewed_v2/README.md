# Benchmark 50 câu (reviewed v2)

50 câu hỏi về luật giao thông đường bộ, cutoff 22/09/2026. Đáp án tham chiếu
được rà với nguyên văn luật (có AI hỗ trợ) và chủ dự án duyệt.

| File | Nội dung |
| --- | --- |
| `cases.jsonl` | Câu hỏi, đáp án tham chiếu, ý bắt buộc/bổ sung, nguồn căn cứ, tiêu chí trạng thái |
| `REVIEWED.md` | Bản đọc của 50 câu |
| `review_decisions.json` | Lý do và hash trước/sau của mỗi thay đổi so với bộ nhãn trước |
| `manifest.json` | Phê duyệt và checksum các file |
| `case.schema.json` | Schema của một câu |

45 câu cần trả lời trực tiếp; 5 câu có điều kiện (016, 042, 044, 046, 048)
chấp nhận trả lời theo điều kiện, hỏi rõ hoặc trả lời một phần.

Quy tắc chấm:

- Không chấm exact match; chấm tương đương về nghĩa với từng ý bắt buộc.
- Ý `required=false` không tính vào mẫu số độ đầy đủ, nhưng nếu được nêu thì
  vẫn phải đúng và có nguồn.
- Các nhóm nguồn thay thế là OR; `match=all` trong một nhóm là AND.
- Nguồn gold ánh xạ sang corpus phục vụ qua `source_processed_ids`.
- Bộ này chưa có câu thiếu nguồn thực sự, nên không dùng để đo khả năng từ chối.

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```
