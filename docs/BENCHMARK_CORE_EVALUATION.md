# Evaluation cốt lõi cho project cá nhân

Chốt 12/10/2026 theo yêu cầu owner tập trung chức năng/kết quả cho CV.
Đây là bổ sung mới, không sửa các protocol/dataset đã khóa checksum.

## Phạm vi thu gọn

- 50 gold reviewed: baseline câu đã biết, dùng phân tích lỗi và cải tiến.
- Development: 54 units đã owner duyệt theo 7 nhóm; freeze version reviewed
  riêng. Chấm 12 end-to-end, 7 replay, 1 rewrite và 34 guards riêng mẫu số.
- Held-out: owner xác nhận đã review/duyệt **gói** 9 câu, ID heldout_001–009,
  version roadlawqa-heldout-nine-delivery-v2, giữ ngoài workspace. 9 thay target
  12 là budget cuối, không ép tạo bù hoặc yêu cầu 2 family/cell. Không tự xác nhận
  coverage, checksum hoặc chất lượng nội dung private khi chưa đọc/kiểm.
- Không cần public receipt/custody workflow phức tạp để bắt đầu engineering.
  Giữ câu/gold riêng tới lúc config chốt; báo rõ owner-reviewed internal gold,
  unseen tương đối với tuning, bộ nhỏ, không production certification.

## Runner và chấm

Chuẩn bị query/history-only inputs; khóa settings/code/snapshot trước run.
Live evaluation chỉ đọc shadow Weaviate và BM25 frozen, không import production
retriever hoặc legacy build scripts. Replay chỉ dùng pool được chỉ định, không
để structural expansion/full retrieval làm đầy pool cố tình thiếu. Accumulation
grade ordered union. Rewrite probe chỉ kiểm tra rewrite, không tính answer score.

Không dùng exact-match hay citation ID membership thay semantic answer accuracy.
Chấm tay hoặc reviewer riêng từng facet 0/0.5/1 theo rubric cũ; lỗi chủ thể,
số/đơn vị/biên/ngày/điều kiện quyết định = 0; 0.5 chỉ thiếu chi tiết không quyết
định và không claim sai. Citation validity deterministic tách khỏi semantic
support chấm theo claim. Conditional trả lời đúng phải thể hiện điều kiện;
abstain đúng phải nêu giới hạn, không khẳng định không phạt.

Report: facet score, all-required-pass, citation validity/support, unsafe
publication, unnecessary abstention, answer rate, evidence completeness,
pipeline errors, median/p95 latency, LLM calls/token/cost khi thực sự đo được.
Chưa review không tự tính đúng; ghi pending. Missing telemetry/cost là null,
không 0. Không gộp legacy/development/held-out hoặc modes thành một điểm.

## Gate tối thiểu và trạng thái

Snapshot frozen, internal gold reviewed/frozen; held-out dùng owner package
approval, không bắt owner duyệt lại riêng từng câu. Trước live run cần query-only
input format hợp lệ, config/code/snapshot lock và đúng resource/model revisions.
Sau run cần semantic reviews mới có answer-quality metrics; không dùng model
outputs để sửa gold/rubric/config rồi vẫn báo là lần held-out độc lập ban đầu.

Giữ C0–C4 labels cho run matrix sau này; lượt triển khai runner này **không chạy
C0–C4**. Không đổi production contract/model/chunking hoặc ingest thêm nguồn.
Các temporal/publication/negative-support blocks vẫn nguyên. Tests/synthetic
smoke chỉ chứng minh công cụ hoạt động, không chứng minh mô hình trả lời đúng.
