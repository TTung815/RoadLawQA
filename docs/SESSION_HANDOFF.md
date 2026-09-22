# Bàn giao session — RoadLawQA V2 Milestone 5

**Cập nhật:** 22/09/2026

**Nhánh:** `v2-foundation`

**Checkpoint trước file bàn giao:** `6afd1b13da20af17398e49ad073a2bd11812ec54`
(`feat: establish milestone 5 corpus baseline`)

## 1. Mục tiêu hiện tại

Milestone 5 phải tạo baseline đánh giá V2 theo pháp luật hiện hành tại
`2026-09-22` trước khi đổi retrieval, chunking, model hoặc kiến trúc.

Thứ tự đã chốt:

1. refresh và audit corpus pháp luật;
2. tạo processed corpus, shadow Weaviate/BM25 và freeze current-law snapshot;
3. làm lại gold answer/citation từ 50 câu lịch sử;
4. thêm regression/challenge và held-out;
5. xây evaluation runner, fixed-evidence replay và chạy ablation C0–C4.

Hiện đang ở cuối bước 1. Nguồn và effective view đã đủ điều kiện để chuẩn bị
snapshot, nhưng processed corpus cuối, shadow index và current-law snapshot chưa
được tạo.

## 2. Việc đã hoàn thành

### Pha 0 — baseline kỹ thuật cũ

- Đã chụp baseline V2/legacy corpus năm 2025 theo chế độ read-only.
- Receipt được commit tại `evaluation/manifests/phase0-baseline.json`.
- Bundle đầy đủ đang ở
  `outputs/evaluation/phase0-baseline-20260918/` (bị `.gitignore`, khoảng 32 MB).
- Baseline có 2.520 chunk, gate integrity đạt, worker probe đạt, không gọi LLM và
  không search. Đây chỉ là baseline tái lập kỹ thuật; không còn là ground truth
  pháp lý hiện hành.

### Benchmark lịch sử

- Đã khôi phục 50 câu từ Google Sheet của chủ dự án vào
  `evaluation/datasets/historical_50/historical_candidates.csv`.
- Checksum và URL nguồn nằm trong
  `evaluation/datasets/historical_50/source_manifest.json`.
- Answer, citation, model output và điểm cũ chỉ được giữ làm lịch sử. Hiện **không
  câu nào có gold theo luật 2026**.
- Không so sánh V1 với V2 trong Milestone 5; không bắt buộc giữ đủ 50 câu sau audit.

### Legal Corpus Refresh

- Scope và cutoff đã được duyệt trong `docs/LEGAL_SCOPE.md`.
- Registry nguồn/checksum/quan hệ văn bản đã được duyệt tại
  `data/legal_sources/registry.json`.
- Bốn nguồn ingest lõi: 49/VBHN-VPQH, 55/VBHN-VPQH, 168/2024/NĐ-CP và
  238/2026/NĐ-CP.
- Audit extraction đạt:
  - 49: 86 Điều, 41 footnote;
  - 55: 89 Điều, 47 footnote;
  - 168: text chủ dự án cung cấp khớp 55/55 Điều với hai PDF Công báo sau khi chỉ
    chuẩn hóa layout;
  - 238: DOCX chính thức và extraction tái lập được.
- Đã xóa hai `extracted-layout.txt` lỗi của 49/55 để tránh dùng nhầm.
- Đã dựng amendment map 168+238 gồm 102 operation lá tại 24 Điều đích.
- Locator/anchor/source line đạt 102/102; effective view có 1.308 locator và áp
  dụng đủ 102 operation.
- Legal review chung và policy fail-closed đã được duyệt. Effective view được phép
  dùng để tạo snapshot/shadow index, nhưng chưa được tự động thay production.

### Git

- Các thay đổi trên đã commit tại `6afd1b1`.
- Trước khi tạo file bàn giao, working tree sạch; không có staged/unstaged diff.
- Chủ dự án muốn commit theo checkpoint có thể kiểm chứng, không chờ hết milestone.
  Checkpoint tiếp theo nên bao gồm processed corpus + shadow index + snapshot receipt.

## 3. Kết luận quan trọng từ legal data

- 49/VBHN-VPQH là canonical reading text của Luật Đường bộ; không index song song
  Luật 35/2024/QH15 để tránh trùng nội dung.
- 55/VBHN-VPQH là canonical reading text của Luật Trật tự, an toàn giao thông
  đường bộ; không index song song Luật 36/2024/QH15.
- Văn bản hợp nhất là nguồn đọc canonical, không phải văn bản thay thế luật gốc;
  lineage và mốc hiệu lực vẫn phải giữ trong metadata.
- 238/2026/NĐ-CP sửa trực tiếp 168/2024/NĐ-CP; **238 không thay thế toàn bộ 168**.
  Corpus xử phạt phải dùng effective view/overlay có provenance tới cả hai nguồn.
- Text layer PDF trang cuối của 49 và 55 bị lỗi. Text corpus phải lấy từ DOCX Công
  báo chính thức; footnote được lưu riêng, không trộn vào body chunk.
- File DOCX 49 từng bị Microsoft Word ghi lại container ZIP trong lúc audit. Nội
  dung và footnote không đổi; file đã được tải lại từ Công báo và khôi phục đúng
  checksum registry. Không mở rồi save lại source DOCX đã khóa checksum.
- Một locator từng bị map sai `điểm đ` thay vì `điểm d` ở khoản 6 Điều 20; đã sửa
  và có regression test.
- Ba locator có mốc 2028 là `mixed_effective_date`, không phải future toàn phần:
  `điểm l khoản 5 Điều 20`, `điểm b khoản 3 Điều 21`, `điểm b khoản 9a Điều 32`.
  Chúng có `active_at_cutoff=null` và `publication_eligible=false`.
- Ba locator có mốc 2029 chưa active:
  `điểm n khoản 5 Điều 20`, `điểm k` và `điểm l khoản 7 Điều 26`.
- Legal review chung **không gỡ publication block** cho ba locator mixed 2028.
  Chỉ mở khi điều kiện thời gian/chủ thể được biểu diễn đủ an toàn và có duyệt
  publication riêng. Không suy luận quy định cũ tiếp tục áp dụng hoặc không có
  chế tài trong giai đoạn chuyển tiếp.
- Luật Xử lý vi phạm hành chính là dependency candidate cho câu hỏi về tuổi/chủ
  thể chịu xử phạt. Chưa ingest; câu cần nguồn này phải abstain.

## 4. Quyết định kiến trúc và dữ liệu đã chốt

- Giữ nguyên hệ thống V2 hiện tại làm baseline; chưa đổi model, chunking, retrieval
  heuristic, reranker hoặc kiến trúc trước evaluation.
- Giữ Pha 0 riêng như historical 2025 baseline; không ghi đè hoặc dùng nó làm gold
  current-law.
- Current-law corpus phải có manifest/checksum và `legal_as_of=2026-09-22`.
- Effective view không được trình bày như văn bản hợp nhất chính thức.
- Mỗi record bị sửa phải giữ citation, `operation_ids`, source document IDs, Điều
  sửa đổi, source line và hash trước/sau patch.
- Fail-closed: thiếu dữ kiện quyết định, thiếu provenance, không rõ mốc áp dụng hoặc
  không đủ negative support thì conditional/abstain; không tự đoán để publish.
- Không ingest thêm toàn bộ luật giao thông. Dependency mới phải xuất phát từ nhóm
  câu hỏi sản phẩm cụ thể và qua scope audit.
- Known regression phải tách khỏi held-out. Held-out chưa cần tạo ngay; nên chốt
  current-law snapshot và audit 50 historical candidates trước.
- Gold schema đã có trường expected evidence, required facets, publication/
  abstention, temporal basis và failure category; scoring fail closed nếu gold chưa
  được duyệt.
- Production collection/index chưa được phép thay đổi trong bước kế tiếp. Dùng tên,
  đường dẫn và receipt riêng cho shadow resources.

## 5. File quan trọng đã tạo hoặc sửa

### Tài liệu

- `AGENTS.md`: quy tắc repository và safety contract.
- `docs/README.md`: context hiện tại và đường dẫn tài liệu chính.
- `docs/MILESTONE_5.md`: roadmap/gate Milestone 5.
- `docs/MILESTONE_5_STATUS.md`: trạng thái ngắn gọn cho chủ dự án.
- `docs/LEGAL_SCOPE.md`: phạm vi câu hỏi, cutoff, dependency gate và citation policy.
- `docs/SESSION_HANDOFF.md`: file bàn giao này.
- `docs/archive/`: verification report cũ chỉ để tham khảo lịch sử.
- `PROJECT_CONTEXT.md`, `docs/MILESTONE_2.md`, `docs/MILESTONE_3.md` và
  `docs/MILESTONE_3_5.md` đã xóa vì stale/trùng nội dung; hai verification report
  3.5/4 được chuyển vào archive.

### Legal source và effective view

- `data/legal_sources/registry.json`: registry canonical, review và checksum.
- `data/legal_sources/amendments_238_2026.json`: 102 amendment operations.
- `data/legal_sources/source_extraction_review.json`: audit 49/55/168.
- `data/legal_sources/nd168_locator_audit.json`: kiểm tra locator/anchor 102/102.
- `data/legal_sources/amendment_review_238_2026.json`: biên bản map/effective view.
- `data/legal_sources/nd168_effective_view_review.json`: quyết định legal review,
  owner policy và publication blocks.
- `data/legal_sources/nd168_effective_view_manifest.json`: input/output hashes,
  trạng thái freeze eligibility và temporal summary.
- `data/processed/current-law/nd168-effective-2026-09-22.json`: effective view
  kỹ thuật 168+238; chưa phải tập chunk cuối để index.
- `data/raw/legal/{49-vbhn-vpqh,55-vbhn-vpqh,168-2024-nd-cp,238-2026-nd-cp}/`:
  nguồn chính thức, supporting text/DOCX và footnote audit.

### Code ingestion/evaluation

- `ingestion/legal_registry.py`: schema registry và freeze gate.
- `ingestion/docx_text.py`: extraction OOXML và footnote audit.
- `ingestion/source_review.py`: audit tái lập text 49/55/168.
- `ingestion/amendment_validator.py`: validate operation/locator/anchor.
- `ingestion/effective_view.py`: dựng overlay 168+238 và temporal metadata.
- `ingestion/corpus_refresh.py`: readiness/source inventory/review packet; output
  chạy thật nằm trong `outputs/corpus-refresh/` và bị ignore.
- `evaluation/snapshot.py`: snapshot tool của Pha 0.
- `evaluation/legacy_probe.py`: kiểm tra contract/BM25 và bind snapshot read-only.
- `evaluation/dataset_schema.py`: schema case/gold/publication/failure categories.
- `evaluation/dataset.py`: recover/audit historical candidates.
- `evaluation/datasets/historical_50/`: CSV nguồn, README và source manifest.
- `.gitattributes`: giữ PDF/DOCX binary và không sửa whitespace của source đã khóa.
- `tests/unit/test_{evaluation_snapshot,evaluation_dataset,legal_corpus_refresh,
  amendment_validator,effective_view}.py`: regression/integrity tests mới.

## 6. Trạng thái data pipeline

```text
Nguồn chính thức + owner text
  → extraction/footnote audit                         ĐẠT
  → registry + metadata/source review                 ĐẠT
  → amendment map 168+238                             ĐẠT (102/102)
  → effective view + legal/fail-closed review         ĐẠT
  → processed current-law chunks                      CHƯA LÀM
  → shadow Weaviate + BM25                            CHƯA LÀM
  → membership/order/runtime verification             CHƯA LÀM
  → current-law snapshot manifest + receipt           CHƯA FREEZE
  → audit/làm lại gold 50 câu                         CHƯA BẮT ĐẦU
  → regression/held-out + C0–C4                       CHƯA BẮT ĐẦU
```

Các file top-level cũ trong `data/processed/*.json`, production `LawChunks` và
`bm25_index.pkl` vẫn là corpus legacy. Chúng chưa được rebuild hoặc ghi đè.

## 7. Vấn đề và điểm chưa giải quyết

- `backend/clean_and_split.py` hard-code ba nguồn luật cũ và output top-level;
  không thể chạy nguyên trạng cho current-law corpus.
- `backend/build_index.py` **xóa collection `LawChunks` hiện tại** rồi index mọi
  JSON top-level. Không chạy script này cho bước shadow.
- `backend/retriever_custom.py` dùng collection `LawChunks`, cache
  `bm25_index.pkl` theo working directory và phụ thuộc order lấy từ Weaviate.
  Shadow build phải cô lập collection/cache và kiểm tra thứ tự BM25.
- `evaluation/snapshot.py` là tool Pha 0: `load_processed()` chỉ đọc
  `data/processed/*.json`, không đọc `data/processed/current-law/`. Chạy nguyên
  trạng sẽ chụp corpus legacy, không phải corpus hiện hành.
- Chưa chốt processed chunk schema/ID cho 49, 55 và effective 168+238. Cần giữ
  các field legacy retrieval đang dùng, đồng thời thêm legal/temporal provenance
  mà không làm production hiểu sai completeness.
- Chưa quyết định chính xác tên shadow collection, đường dẫn BM25 shadow và receipt
  current-law. Quyết định nên rõ ràng, cấu hình được và không đụng resource cũ.
- Full Pha 0 bundle ở `outputs/` không được commit; receipt có ghi rõ một mình receipt
  không đủ replay nếu bundle local bị mất.
- Các locator mixed/future không được dùng làm publishable gold trong trạng thái hiện tại.

Điểm conversation cũ không còn đúng với repo hiện tại:

- “49 có 85 Điều” là sai; nguồn DOCX chính thức có **86 Điều**.
- “49/55/168 còn pending review” đã cũ; registry hiện ghi tất cả nguồn ingest đã
  approved.
- “Effective view/legal review còn pending” đã cũ; review chung hiện approved,
  nhưng publication block riêng của sáu locator vẫn còn.

## 8. Command và kết quả quan trọng

Đã chạy thành công:

```bash
.venv/bin/python -m ingestion.source_review
# Source extraction review: passed

.venv/bin/python -m ingestion.amendment_validator
# 102 operations; 102 passed; 0 failed; freeze_allowed=true

.venv/bin/python -m ingestion.effective_view
# 1.308 effective locators; 102 applied; 0 failed

.venv/bin/python -m ingestion.corpus_refresh
# technical_source_gate_passed=true; freeze_eligible=true; blocking_reasons=[]

.venv/bin/python -m pytest -q
# 349 passed, 1 deselected

git diff --check
# đạt sau khi khai báo source artifacts trong .gitattributes
```

Pha 0 trước đó:

- live snapshot gate đạt với 2.520 chunk;
- worker probe đạt trên CPU, đúng model revisions, `llm_calls=0`, `search_calls=0`;
- tại thời điểm Pha 0: 299 test đạt, 1 deselected.

## 9. Công việc đang dở

Không có code implementation dở trước khi tạo handoff. Thay đổi duy nhất sau
checkpoint `6afd1b1` là:

- làm rõ publication block trong `ingestion/effective_view.py` và review artifact;
- tái tạo manifest/checksum liên quan;
- thêm file bàn giao này.

Session mới phải chạy `git status` và xem diff/commit mới nhất trước khi tiếp tục.

## 10. Task tiếp theo nên thực hiện

Thực hiện **processed current-law corpus + shadow index preflight** theo phạm vi nhỏ:

1. định nghĩa contract chunk/ID/metadata cho 49, 55 và effective 168+238;
2. tạo builder deterministic vào thư mục current-law riêng;
3. thêm validation cho article/locator coverage, duplicate ID, citation,
   `legal_as_of`, temporal status và publication eligibility;
4. build Weaviate collection shadow với tên riêng, không xóa `LawChunks`;
5. build BM25 shadow từ đúng ordered membership của collection shadow;
6. so sánh processed ↔ indexed ↔ runtime order, kiểm tra vector/schema/model
   provenance và tạo manifest/receipt;
7. chỉ khi tất cả gate đạt mới đánh dấu current-law snapshot frozen;
8. vẫn chưa chạy benchmark hoặc sửa production retrieval trong task này.

Trước khi code, nên viết một kế hoạch ngắn cho contract/output paths và xác nhận
script nào được phép tái sử dụng. Không chạy `backend/build_index.py` nguyên trạng.

## 11. File session mới nên đọc trước

Theo thứ tự:

1. `AGENTS.md`
2. `docs/SESSION_HANDOFF.md`
3. `docs/MILESTONE_5_STATUS.md`
4. `docs/MILESTONE_5.md`
5. `docs/LEGAL_SCOPE.md`
6. `data/legal_sources/registry.json`
7. `data/legal_sources/source_extraction_review.json`
8. `data/legal_sources/nd168_effective_view_review.json`
9. `data/legal_sources/nd168_effective_view_manifest.json`
10. `ingestion/effective_view.py`
11. `ingestion/corpus_refresh.py`
12. `backend/clean_and_split.py`, `backend/build_index.py` và
    `backend/retriever_custom.py` để thấy các rủi ro legacy/destructive
13. `evaluation/snapshot.py` và `evaluation/legacy_probe.py`
14. `evaluation/datasets/historical_50/README.md` — chỉ đọc sau khi hiểu snapshot gate
