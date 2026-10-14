# Current-law gold — owner-reviewed v1

Ngày chốt: **11/10/2026**. Cutoff pháp luật: **22/09/2026**.
Snapshot vẫn `roadlawqa-current-law-2026-09-22`; không bổ sung nguồn vào index.

50 câu được chủ dự án duyệt bằng feedback và chấp thuận phương án sửa trong
hội thoại. Ghi nhận đúng owner review cho benchmark nội bộ; không giả định
chuyên môn luật sư hay một reviewer độc lập bổ sung. Đã lưu cả nội dung review
ban đầu, quyết định từng câu và chấp thuận biên tập, không chỉ đổi nhãn hàng loạt.

| Kết quả | Số câu |
| --- | --- |
| Gold approved | 50 |
| Publish | 41 |
| Conditional | 5 |
| Abstain | 4 |
| Giữ / sửa query so với CSV lịch sử | 18 / 32 |

## Xem ở đâu

- [REVIEWED.md](REVIEWED.md): câu hỏi/đáp án cuối, ý bắt buộc, căn cứ và ghi chú
  reviewer riêng bằng tiếng Việt; không cần hiểu f1/g1 để đọc.
- [review_feedback.txt](review_feedback.txt): ghi chú của chủ dự án, chỉ chuẩn hóa
  xuống dòng; checksum attachment gốc nằm ở source_recovery.json.
- [review_authorization.md](review_authorization.md): phương án đã giải thích và
  câu trả lời chấp thuận tiếp theo của chủ dự án.
- [review_decisions.json](review_decisions.json): từng approval, thay đổi chính xác,
  lý do, reviewer/date; câu 24 được chốt qua follow-up, không giả là đã duyệt ban đầu.
- [cases.jsonl](cases.jsonl): gold machine-readable, giữ lịch sử và parent hash.
- [evidence_catalog.json](evidence_catalog.json): full text/context/provenance của
  các chunk đã dùng, không trộn thêm nguồn web vào retrieval corpus.
- [manifest.json](manifest.json), [freeze_receipt.json](freeze_receipt.json): khóa
  input/output/protocol/tool và binding tới snapshot/draft.

## Điểm thay đổi sau review

- Lời nhắc reviewer/chấm được chuyển khỏi reference answer; không bắt model
  lặp lại jargon hay đoạn cảnh báo về benchmark không thuộc câu hỏi.
- Câu 4/11 bỏ cutoff khỏi query, giữ GPLX cấp mới; cutoff vẫn ở metadata.
- Câu 9 giữ ngày 01/02/2025, chuyển abstain → publish. Có temporal review riêng
  khoản 2 Điều 58, đối chiếu luật gốc và VBHN; mốc đủ 12 tháng 01/02/2026.
  Không khẳng định hệ thống dữ liệu thực tế đã cập nhật hay mở lịch sử toàn corpus.
- Câu 24 giữ trọng tâm thiếu trang bị, làm rõ loại xe thuộc phạm vi bắt buộc và
  thiếu cả đèn/tấm phản quang phía trước; dùng khoản 1 Điều 15 NĐ 168.
- Câu 39 diễn đạt tài xế thuê không phải chủ xe, bổ sung căn cứ phân định chủ thể
  tại Điều 47 và cách dẫn NĐ 168 đã sửa bởi 238.
- Câu 42 vẫn conditional, sửa diễn đạt làn/dải khẩn cấp và citation amendment;
  chunk frozen đã có operation của 238, không rebuild corpus.
- Câu 10/29 giữ abstain do policy negative-support hiện tại; câu 23/43 giữ
  abstain do Luật XLVPHC chưa trong snapshot. Không thay câu để loại hết abstention.

## Kiểm tra

```bash
.venv/bin/python -m evaluation.reviewed_current_law_dataset verify
.venv/bin/python -m evaluation.current_law_dataset verify
.venv/bin/python -m evaluation.current_law_snapshot --verify
.venv/bin/python -m pytest -q
```

Tool reviewed dùng contract riêng có scoped temporal review; tool draft cũ
không chấp nhận publish lịch sử bằng ngoại lệ này. `require_reviewed_scoring`
chỉ nhận subset đã approved từ bundle frozen đã verify. Gold gate đạt **không
mở C0–C4**: còn Pha 3 regression/challenge/held-out và Pha 4 runner/replay.

Builder/freeze create-only, không ghi đè artifacts/receipt. Sửa sau freeze cần
version mới; không sửa checksum receipt để hợp thức hóa sửa gold. Thư mục
draft `../current_law_20260922/` và CSV lịch sử vẫn giữ nguyên byte/checksum.

## Khôi phục DOCX nguồn

Hai DOCX 49/55 được Word-like save làm thay đổi container/checksum, nhưng
body text và footnote vẫn khớp bản extraction đã khóa. Đã giữ bản sao trước
khôi phục trong `outputs/source-recovery-20261011.CcHpDP/` (ignored), rồi khôi
phục đúng HEAD blob khớp registry. [source_recovery.json](source_recovery.json)
ghi hash trước/sau và đường dẫn backup. Không sửa registry hoặc snapshot hash;
backup không phải nguồn để scoring và không bắt buộc để replay dataset.
