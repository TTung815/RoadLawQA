# Benchmark reviewed v1 — bổ sung sau owner review

Ngày chốt: 11/10/2026. Cutoff corpus vẫn 22/09/2026.
Đọc cùng [protocol draft v1](BENCHMARK_PROTOCOL.md); không sửa protocol/artifact
draft đã khóa checksum. Đây là benchmark nội bộ V2, không chứng nhận production.

## Review và phiên bản

Chủ dự án đã review AUDIT.md và gửi ghi chú cho 50 câu: 49 câu ghi Duyệt,
câu 24 yêu cầu làm rõ. Sau khi nhận giải thích về các câu 1/4/9/11/23/24/39/42/43,
chủ dự án đồng ý áp dụng phương án sửa. Lưu cả feedback, quyết định từng câu,
thay đổi so với draft và chấp thuận tiếp theo; không giả định có reviewer luật
chuyên nghiệp hoặc thêm một lượt review độc lập chưa diễn ra.

Dataset mới `current_law_20260922_reviewed_v1` giữ query gốc, lịch sử, family,
exposure và snapshot. Các thay đổi biên tập theo ủy quyền được ghi rõ; không
ghi rằng người duyệt đã đọc nguyên văn phiên bản cuối nếu thực tế chỉ chốt
phương án sửa. Approval là owner review để đánh giá nội bộ.

## Thời gian và câu 9

Ngày hỏi khác cutoff không tự động đồng nghĩa thiếu nguồn. Muốn publish một
câu lịch sử phải có review hiệu lực riêng cho chính các căn cứ được dùng,
interval bao phủ ngày sự kiện và mốc kết quả, source/context hashes, nguồn
đối chiếu và reviewer/date. Không suy từ ngày ban hành chung của văn bản.

Câu 9 có review riêng khoản 2 Điều 58: quy tắc phục hồi sau 12 tháng đã có ở
Luật 36/2024/QH15 (PDF Công báo, trang PDF 33) và không đổi trong 55/VBHN-VPQH
(trang PDF 48). Căn cứ retrieval/gold vẫn là chunk 55 trong snapshot. Đối chiếu
luật gốc chỉ là provenance review, không index bản luật gốc hoặc mở corpus mới.
Interval đã review: 01/01/2025–22/09/2026; sự kiện 01/02/2025 và mốc đủ 12 tháng
01/02/2026 nằm trong interval này. Không suy rộng approval sang các điều khác.

Validator reviewed chỉ cho ngoại lệ thời gian khi toàn bộ support refs được
review bao phủ và đáp ứng metadata/source hashes. Tool draft vẫn giữ contract
cũ; production temporal/negative-support contract không được thay đổi.

## Query và đáp án

- Cutoff nằm trong metadata/run context; không bắt buộc có trong mọi query.
  Các câu không chủ đích kiểm tra ngày có thể hỏi tự nhiên, vẫn giữ điều kiện
  quyết định như GPLX cấp mới hoặc tài xế không phải chủ phương tiện.
- Reference answer chứa nội dung trả lời người dùng. Lời nhắc chấm, phạm vi
  benchmark, cảnh báo đối chiếu gold cũ nằm ở reviewer notes. Đây không phải
  đáp án exact-match; không bắt model lặp lại văn phong hay internal jargon.
- Câu 24 kiểm tra xe thiếu trang bị theo khoản 1 Điều 15 NĐ 168, không tự đổi
  sang hành vi không sử dụng đèn/báo hiệu ban đêm theo điểm i khoản 1 Điều 9.
  Query nói rõ loại xe thuộc phạm vi bắt buộc trang bị và thiếu cả hai phương
  án đèn/tấm phản quang ở phía trước. Không suy cộng hai mức phạt.
- Câu 39 giữ phạm vi tài xế không phải chủ xe; ghi căn cứ Điều 47 và sửa đổi 238.
- Câu 42 giữ conditional; dẫn 168 đã sửa bởi 238, bao gồm làn/dải dừng khẩn cấp.
- Câu 23/43 giữ missing-dependency abstain. Câu 10/29 giữ policy abstain đã duyệt;
  đây là expectation của hệ thống có phạm vi giới hạn, không tuyên bố pháp luật
  không có lời giải. Không ingest 90/VBHN-VPQH chỉ để nâng điểm benchmark.

## Freeze và gate

Reviewed builder/verifier nằm ở `evaluation.reviewed_current_law_dataset`.
Build create-only; freeze chỉ sau khi tất cả selected gold được duyệt, source/
snapshot/draft/review/protocol/artifact hashes khớp, không có open review items.
Freeze receipt khóa manifest/artifacts; thay đổi sau freeze cần phiên bản mới,
không cập nhật receipt để hợp thức hóa thay đổi.

Gold gate đạt không mở C0–C4: Pha 3 vẫn thiếu regression/challenge và unseen
held-out, Pha 4 vẫn thiếu runner/replay. Không chạy model hay thay index ở Pha 2.
Rubric/scoring của protocol gốc giữ nguyên. Báo cáo phải phân biệt owner-reviewed
gold readiness với benchmark/production readiness.
