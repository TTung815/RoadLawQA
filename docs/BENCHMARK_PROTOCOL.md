# Protocol benchmark RoadLawQA V2 — bản 1

Ngày lập: 09/10/2026. Trạng thái: protocol kỹ thuật cho audit draft, chưa có
gold được duyệt hoặc kết quả chạy hệ thống.

## Mục tiêu và giới hạn

Đánh giá V2 có tìm đủ căn cứ, trả lời đúng và đủ từng yêu cầu, dẫn nguồn đúng,
và xử lý thiếu dữ kiện/nguồn an toàn hay không. Bộ đầu tiên là benchmark nội bộ
để tìm lỗi và so sánh cấu hình V2. Điểm của bộ này không đại diện cho mọi câu hỏi
giao thông hoặc chứng minh sẵn sàng production. Không so điểm V1 với V2.

Corpus duy nhất: snapshot `roadlawqa-current-law-2026-09-22`, cutoff 22/09/2026.
Ngày audit 09/10/2026 không mở rộng cutoff. Câu có ngày khác phải ghi ngày rõ ràng
và chỉ được trả lời chắc chắn nếu snapshot có đủ căn cứ cho ngày đó.
Effective view 168+238 là artifact kỹ thuật; 49/55 là văn bản hợp nhất, không
đổi tên thành "Luật 49/55". Không ingest dependency khi xây dataset.

## Đơn vị đánh giá và sửa câu hỏi

Một case gồm query đã audit, query gốc, quyết định keep/edit/drop và lý do,
historical ID, family ID, loại câu, challenge tags, expected answer, required
facets, evidence groups, temporal basis, publication và review record.

- Giữ nguyên byte/checksum của CSV gốc. Dataset dẫn xuất lưu raw source row.
- Bỏ số hiệu hoặc số Điều cung cấp sẵn đáp án khi mục tiêu là tìm căn cứ tự nhiên.
  Chỉ giữ citation trong query nếu đang kiểm tra tra cứu có chỉ định nguồn.
- Không thay toàn bộ số hiệu 36 bằng 55: luật gốc và VBHN khác vai trò.
- Chuyển "hôm qua", "luật mới", "hiện nay" thành mốc cố định hoặc default cutoff.
- Thêm điều kiện khi cần để cô lập một nhánh; phải ghi rõ đã thêm giả định nào.
- Có thể giữ thiếu dữ kiện có chủ đích, gắn tag `missing_facts` và expectation
  conditional. Không thêm giả định âm thầm để ép tất cả case thành publish.
- Không đổi ngày lịch sử chỉ để corpus trả lời được. Giữ case thời gian ngoài
  snapshot làm bài kiểm tra giới hạn khi có giá trị sản phẩm.
- Drop khi câu trùng ý hoàn toàn, không rõ mục tiêu sau sửa, hoặc không phục vụ
  phạm vi sản phẩm. Không bắt buộc giữ đúng 50 case để scoring.
- Câu đã sửa/paraphrase vẫn `historically_used`, split `legacy`; không làm held-out.
  Biến thể cùng ý/điều khoản/đáp án dùng cùng family để tránh chia sang hai split.

## Ma trận bao phủ

| Trục | Nhóm phải theo dõi |
| --- | --- |
| Nhu cầu | factual, penalty, scenario; nhãn gốc có thể sửa nếu lý do rõ |
| Căn cứ | một locator, nhiều locator, cross-document |
| Độ khó | direct, numeric, boundary, exception, multiple_facets, reasoning |
| Hiệu lực | mặc định cutoff, amended_rule, explicit_date, temporal_gap |
| An toàn | missing_facts, missing_dependency, negative_conclusion |
| Cách hỏi | câu tự nhiên và tra cứu chỉ định nguồn; ghi cue nếu có |

Phân bố 15/15/20 lịch sử là provenance, không phải quota chất lượng. Báo cáo
coverage thực tế và gap; không suy từ số lượng 50 rằng đã bao phủ hết. Bộ lịch sử
chưa có held-out, multi-turn hoặc đầy đủ các biên ngày 2028/2029. Các nhóm thiếu
thuộc Pha 3, không được sinh thêm chỉ để tăng tổng điểm trong Pha 2.

## Xây gold và review

1. Kiểm tra receipt, full shadow bundle, inputs và source CSV trước audit.
2. Chọn evidence từ processed current-law chunks bằng stable ID. Đọc cả `text`,
   `clause_head`, `enriched_text`, metadata temporal và source spans. Khoản mở đầu
   của một điểm có thể chứa mức tiền hoặc giới hạn số người; leaf text riêng
   chưa đủ. Tên luật/Điều chỉ là định vị, không chứng minh áp dụng.
3. Với mỗi required facet, ghi điều cần trả lời và evidence group chứng minh nó.
   `all` nghĩa là cần đồng thời tất cả leaf; `any` chỉ dùng cho nguồn thực sự
   thay thế được. Tiền và điểm phải có facet riêng; không suy điểm từ mức tiền.
4. Reference answer viết lại từ evidence, không copy gold/model output lịch sử.
   Evidence gốc phải có stable ID, shadow UUID, citation và hash text/context.
5. `publish`: mọi required facet có positive support, đủ dữ kiện, đúng thời gian,
   không dùng chunk publication-blocked làm support và không thiếu dependency.
6. `conditional`: nêu dữ kiện/nhánh chưa xác định; không công bố một nhánh như
   sự thật. Contract V2 hiện có thể trả `insufficient_evidence`; ghi allowed
   statuses theo contract hiện tại, không tự thêm endpoint/status mới.
7. `abstain`: nêu thiếu nguồn/temporal provenance/negative-support provenance;
   không biến thiếu nguồn thành "không phạt". Có thể ghi evidence context cho
   phần đã biết; context không trở thành support cho kết luận đầy đủ.
8. Codex author draft/technical audit với ngày và findings; `gold.review` giữ
   `needs_review`. Người duyệt nội dung độc lập kiểm tra source, facet, tiền,
   điểm, ngoại lệ và thời gian; ghi reviewer/date trước `approved`.
   Không giả danh người duyệt hoặc coi user đồng ý làm task là duyệt 50 đáp án.
9. Chốt phiên bản dataset/checksum trước xem output của cấu hình sẽ đánh giá.
   Nếu gold sửa sau khi xem output, tạo phiên bản mới và rerun các cấu hình.

## Pilot và gate Pha 2

Pilot 10 historical ID: 1, 2, 5, 7, 9, 16, 23, 36, 43, 48. Chúng kiểm tra
quy tắc/định nghĩa, tiền+điểm, sửa đổi, khoảng số, ngày lịch sử, ngoại lệ,
thiếu dữ kiện và dependency. Pilot là thử protocol/schema/provenance, không
chạy model và không chứng minh gold pháp lý đúng. Ghi findings pilot trước
khi expand cùng protocol sang 50 candidate.

Gate kỹ thuật: đủ 50 decision record, source không đổi, query revision truy
nguyên được, ID/family rõ, evidence/hash/context khớp snapshot, không support
chunk blocked, expectation nhất quán, pilot đầy đủ, report coverage/gap.
Gate scoring: tập selected không rỗng, chỉ gồm case không drop có gold approved,
reviewer/date và snapshot/protocol hashes đúng. Không yêu cầu approved đủ 50;
mọi case needs_review bị loại khỏi scoring. Gate kỹ thuật đạt không mở C0–C4.

## Rubric khi có runner (Pha 4)

| Metric | Cách tính dự kiến |
| --- | --- |
| Required-facet accuracy/completeness | Chấm từng facet 0/0.5/1 với quy tắc partial riêng; báo all-required-pass theo case |
| Evidence completeness@k | Group `all` đủ khi mọi leaf cần có; group `any` đủ khi có một nguồn hợp lệ; context không tính support |
| Citation validity và support | Tách citation tồn tại/đúng locator khỏi nội dung nguồn thực sự hỗ trợ claim |
| Unsafe publication | Tỷ lệ case cần conditional/abstain nhưng vẫn công bố kết luận chắc chắn không có support |
| Unnecessary abstention | Tỷ lệ publish case đủ căn cứ mà hệ thống không trả lời |
| Coverage | Tỷ lệ đã trả lời, đi kèm accuracy trên phần đã trả lời; không thưởng từ chối mọi case |
| Stage errors, latency, cost | Retrieval/grade/rewrite/expansion/generation/verification; median/p95 và token/cost |

Không dùng exact string match cho toàn đáp án. Số/đơn vị/biên khoảng, chủ thể và
ngày cần đúng; paraphrase hợp nghĩa được chấp nhận. Claim vượt phạm vi gold phải
review support riêng. Không gom thành một điểm trung bình che lỗi unsafe; báo
theo query type, challenge tag và family, luôn ghi tử số/mẫu số.
Chưa đặt ngưỡng production từ bộ 50 nhỏ; với held-out sau này báo uncertainty
theo family để các paraphrase không tạo cảm giác nhiều mẫu độc lập.

Quy tắc điểm facet khi triển khai runner: 1 nếu đúng và đủ điều bắt buộc; 0.5
nếu chỉ thiếu chi tiết không quyết định áp dụng và không có claim sai; 0 nếu
thiếu toàn facet hoặc sai. Sai chủ thể, số tiền, điểm, đơn vị, biên khoảng, ngày
hoặc điều kiện quyết định luôn là 0, không partial credit. Một case chỉ
all-required-pass nếu tất cả required facets đạt 1 và citation support đạt.
Publication unsafe là cờ riêng, không được bù bằng điểm văn phong/relevance.
Reviewer phải ghi lý do cho partial/disagreement; dùng cùng rubric cho các
cấu hình, không sửa rubric sau khi biết cấu hình nào được lợi.

## Artifact và thao tác

`evaluation/datasets/current_law_20260922/draft_labels.json`: nhãn audit viết tay.
`cases.jsonl`: case dẫn xuất, schema kế thừa gold contract hiện có.
`AUDIT.md`: bảng và chi tiết từng câu, có câu gốc/mới, đáp án draft, facets,
evidence, provenance, open review items.
`PILOT.md`: 10 câu thử và findings. `audit.json`: coverage/gates machine-readable.
`manifest.json`: source/snapshot/protocol/tool/artifact hashes.

Builder/auditor riêng `evaluation.current_law_dataset` đọc current-law snapshot,
không dùng trực tiếp `evaluation.dataset recover/audit` của Pha 0. Tool cũ vẫn
giữ contract lịch sử. Không chạy production retrieval, model hoặc C0–C4 ở bước này.
