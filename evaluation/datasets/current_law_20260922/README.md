# Current-law candidate audit — v1 draft

Ngày audit: 09/10/2026. Legal cutoff: **22/09/2026**, không phải ngày audit.

Đã áp dụng [protocol](../../../docs/BENCHMARK_PROTOCOL.md) vào pilot 10 câu rồi
50 historical candidate. Đây là đáp án/nhãn dự thảo dựa trên snapshot;
**0/50 gold được independent legal review và chưa được dùng scoring**.

| Kết quả | Số câu |
| --- | --- |
| Giữ câu hỏi | 18 |
| Sửa câu hỏi | 32 |
| Loại | 0 |
| Publish dự kiến | 40 |
| Conditional dự kiến | 5 |
| Abstain dự kiến | 5 |

Không bắt buộc giữ 50 sau review. Loại và expectation là hai quyết định khác
nhau: câu cần abstain có giá trị kiểm tra giới hạn, không nhất thiết bị loại.
Tất cả câu, kể cả câu sửa, vẫn historically_used/legacy; chưa có held-out.

## Đọc và review ở đâu

- [AUDIT.md](AUDIT.md): bảng quyết định và chi tiết **từng câu**, gồm câu gốc,
  câu sửa, lý do, reference answer draft, facets, evidence và open review items.
- [PILOT.md](PILOT.md): 10 câu thử protocol và findings đã áp dụng.
- [draft_labels.json](draft_labels.json): nhãn viết tay, không lấy answer cũ làm gold.
- [cases.jsonl](cases.jsonl): dataset dẫn xuất, một case trên một dòng.
- [evidence_catalog.json](evidence_catalog.json): toàn bộ chunk được viện dẫn, có
  text, clause head, enriched context, temporal status, nguồn/dòng và checksum.
- [audit.json](audit.json), [manifest.json](manifest.json): coverage/gate và hashes.

Ví dụ câu 1 bỏ số hiệu luật khỏi query; citation vẫn truy nguyên về 55/VBHN-VPQH.
Câu 4/11 làm rõ GPLX cấp mới; câu 41 thay "hôm qua" bằng 22/09/2026.
Câu 9 giữ ngày 2025 và expectation abstain vì thiếu temporal replay.
Câu 23/43 cần dependency Luật Xử lý vi phạm hành chính; không ingest thêm.
Câu 10/29 giữ abstain do policy negative-support hiện tại, kèm điểm reviewer
cần xem lại để tránh unnecessary abstention. Các case conditional không tự
chọn một nhánh khi thiếu facts.

## Kiểm tra và tái lập

```bash
.venv/bin/python -m evaluation.current_law_dataset verify
.venv/bin/python -m pytest tests/unit/test_current_law_dataset.py -q
```

Verify đọc frozen receipt/full shadow bundle, kiểm tra raw/extraction hashes,
CSV gốc, protocol/tool/schema hashes và tái tạo artifact để so sánh byte-for-byte.
Không cần Weaviate live, embedding/reranker hoặc LLM. Source CSV gốc được giữ tại
`../historical_50/`; checksum vẫn `d700e5adec9a869717b06034641a0d654d6c294c4f93e3d5449e934ee8ac856b`.

Nếu cần tái lập sang thư mục **mới**:

```bash
.venv/bin/python -m evaluation.current_law_dataset build \
  --directory outputs/current-law-dataset-replay-v1 \
  --labels evaluation/datasets/current_law_20260922/draft_labels.json
```

Builder không ghi đè dataset đã tồn tại và không tự approve. Phiên bản draft
là input để reviewer duyệt; khi chốt hoặc sửa gold, tạo phiên bản reviewed mới
có review record và manifest riêng, không chỉnh case rồi giữ manifest cũ.
`require_current_law_scoring` chấp nhận approved subset bất kỳ, nhưng từ chối
case pending/excluded, unresolved review items, blocked support hoặc evidence
không khớp snapshot. Không dùng CLI audit Pha 0 cho bundle current-law này.

## Việc còn lại

Review pilot rồi từng case còn lại, giải quyết open review items, chốt query/
answer/evidence/facets/expectation và reviewer/date. Sau đó freeze dataset
reviewed và sang Pha 3–4. Chưa chạy C0–C4, chưa thay production retrieval/index.
Coverage gaps trong audit.json gồm held-out, multi-turn, biên hiệu lực và
dependency; bộ 50 này chưa chứng minh chất lượng production.
