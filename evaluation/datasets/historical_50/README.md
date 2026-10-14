# 50 câu benchmark lịch sử

## Trạng thái hiện tại

- [historical_candidates.csv](historical_candidates.csv) là nguồn câu hỏi đầy đủ
  nhất lấy từ Google Sheet của chủ dự án.
- Giữ cả đáp án và citation cũ chỉ để tham khảo nguồn gốc câu hỏi.
- **Không câu nào có gold hiện hành.** Toàn bộ answer, citation, required facets
  và expected publication trong CSV này chỉ là lịch sử. Draft hiện hành được
  viết lại riêng tại [current_law_20260922](../current_law_20260922/README.md);
  chưa có gold approved và CSV nguồn này giữ nguyên.
- Không dùng điểm/model output cũ để so sánh V1 với V2.

Các bundle trung gian `v1/`, `v2/`, `v3/`, draft labels và audit theo corpus cũ
đã được xóa sau khi giữ lại nguồn candidate đầy đủ cùng checksum.

## Khi nào bắt đầu làm gold mới?

Chỉ bắt đầu sau khi:

1. corpus 49/55 và effective view 168+238 đã được duyệt;
2. current-law snapshot được freeze;
3. schema gold mới được chốt.

Khi đó từng câu được giữ, sửa hoặc loại theo chất lượng câu hỏi. Không bắt buộc
phải giữ đủ 50 câu.
