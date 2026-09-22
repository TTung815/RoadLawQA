# Milestone 5 — Corpus hiện hành và baseline đánh giá

## Mục tiêu

Tạo corpus pháp luật có hiệu lực tại `2026-09-22`, đóng băng snapshot mới, làm
lại gold/citation và đo V2 trước khi đổi retrieval, chunking, model hoặc kiến trúc.

## Roadmap

| Pha | Việc chính | Trạng thái |
| --- | --- | --- |
| 0 | Giữ receipt kỹ thuật của V2 năm 2025 | Hoàn tất, chỉ để tái lập; không dùng so điểm pháp lý. |
| 1 | Refresh corpus và freeze current-law snapshot | Nguồn/effective view đã duyệt; đang chờ processed corpus và shadow index. |
| 2 | Làm lại gold/citation từ 50 câu lịch sử | Chờ Pha 1. |
| 3 | Thêm regression/challenge và held-out | Chờ Pha 2. |
| 4 | Evaluation runner, metrics, fixed-evidence replay | Chờ dataset đã duyệt. |
| 5 | Chạy C0–C4 và báo cáo ablation | Chờ snapshot và gold đã khóa. |

Không rebuild production index và không chạy benchmark C0–C4 trước khi Pha 1 đạt.

## Pha 1 — Corpus pháp luật hiện hành

### Nguồn lõi

- `49/VBHN-VPQH`: bản đọc hiện hành của Luật Đường bộ.
- `55/VBHN-VPQH`: bản đọc hiện hành của Luật Trật tự, an toàn giao thông đường bộ.
- `168/2024/NĐ-CP`: nghị định gốc về xử phạt.
- `238/2026/NĐ-CP`: sửa đổi trực tiếp 168, không thay thế toàn bộ 168.

Phạm vi chi tiết nằm ở [LEGAL_SCOPE.md](LEGAL_SCOPE.md). Không ingest thêm văn
bản nếu chưa có nhóm câu hỏi cụ thể cần nguồn đó.

### Đã hoàn thành

- Registry nguồn, URL, checksum và quan hệ văn bản.
- PDF chính thức của 49, 55, 168 và 238.
- TXT 168 do chủ dự án cung cấp nằm cùng thư mục nguồn 168.
- DOCX 238 trùng từng byte với file từ Công báo; extraction tái lập được.
- Tách đủ 86 Điều của 49, 89 Điều của 55, 55 Điều của 168 và 21 Điều của 238.
- Chuẩn hóa amendment map thành **102 operation lá tại 24 Điều đích**.
- Validator kiểm tra **102/102 locator và phrase anchor đạt**.
- Sửa lỗi map: khoản 6 Điều 19 của 238 trỏ tới **điểm d khoản 6 Điều 20**,
  không phải điểm đ.
- Đã dựng và duyệt effective view: 1.308 locator, áp dụng đủ 102 operation;
  1.302 locator active tại cutoff, 3 locator mixed mốc 2028 bị chặn publication
  và 3 locator chưa hiệu lực tới năm 2029.
- Đã duyệt policy fail-closed cho các locator có điều kiện thời gian/chủ thể.
- Đã audit extraction 49/55/168; không còn nguồn ingest chờ duyệt.

Biên bản kỹ thuật:

- `data/legal_sources/amendment_review_238_2026.json`
- `data/legal_sources/nd168_locator_audit.json`
- `data/legal_sources/nd168_effective_view_manifest.json`
- `data/processed/current-law/nd168-effective-2026-09-22.json`

### Còn phải làm

1. Tạo processed corpus và shadow Weaviate/BM25 mới.
2. Kiểm tra processed/index/runtime/BM25 rồi freeze current-law snapshot.

### Gate hoàn tất Pha 1

- Mọi nguồn ingest có metadata và extraction được duyệt.
- Effective view 168+238 qua kiểm tra kỹ thuật và legal review. **Đạt.**
- Build lặp lại cho cùng checksum/ID.
- Shadow index và BM25 khớp membership/thứ tự.
- Snapshot mới có manifest, checksum và receipt; production index chưa bị ghi đè.

## Pha 2 — Làm lại benchmark

50 câu cũ chỉ là **historical candidates**. Không tái sử dụng mặc định answer,
citation, model output hoặc điểm cũ làm gold hiện hành.

Với mỗi câu:

- giữ, sửa câu hỏi hoặc loại;
- viết lại reference answer theo snapshot hiện hành;
- gắn expected evidence/citation, required facets và mốc áp dụng;
- chốt publish, conditional answer hoặc abstain;
- ghi người/ngày duyệt.

Không bắt buộc giữ đủ 50 câu. Không so V1 với V2 trong Milestone 5.

## Pha 3–5 — Evaluation

- Tách known regression khỏi held-out.
- Ghi kết quả theo stage: retrieval, coverage, rewrite/retry, expansion,
  accumulated evidence, generation và verification.
- Đo retrieval quality, evidence completeness, lỗi grading/rewrite, expansion,
  answer/citation, unsafe publication, abstention, latency và cost.
- Fixed-evidence replay tách lỗi retrieval khỏi generation/verification.
- C0 đầy đủ; C1 tắt reranker; C2 tắt retry/rewrite; C3 tắt expansion; C4 tắt
  verification chỉ trong evaluation offline.

## Nguyên tắc giữ nguyên

- Không nới chính sách an toàn pháp lý.
- Không coi thiếu evidence là bằng chứng không áp dụng.
- Không đổi model, chunking hay retrieval heuristic trước baseline.
- Receipt Pha 0 được giữ để tái lập kỹ thuật, không dùng làm ground truth hiện hành.
