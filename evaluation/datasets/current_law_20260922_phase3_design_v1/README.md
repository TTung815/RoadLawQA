# Pha 3 — design v1 và draft development

Cutoff 22/09/2026, lập 11/10/2026. Không sửa gold 50 đã freeze hoặc corpus/index.

- [COVERAGE.md](COVERAGE.md): coverage thực tế, khoảng trống và blueprint held-out.
- [DEVELOPMENT.md](DEVELOPMENT.md): 16 bài mới cần review, có query/history,
  đáp án toàn corpus, mục tiêu lỗi, pool replay và căn cứ. **0 bài approved**.
- [plan.json](plan.json): recipes, suites còn cần author và 6 cell held-out.
- [coverage.json](coverage.json): counts và conservative family/article exclusion
  inventory, không phải kết quả chạy hệ thống.
- [development_cases.jsonl](development_cases.jsonl): contract mới, không bịa
  CSV row cho câu dẫn xuất. Parent gold được tham chiếu, không kế thừa approval.
  Vẫn `legacy/historically_used`, cùng family; `suite=development` chỉ vai trò.
- [evidence_catalog.json](evidence_catalog.json): full context/source spans/hashes
  của gold và distractor pool từ snapshot đã freeze.
- [manifest.json](manifest.json): hash binding parent/snapshot/plan/protocol/tool.
- [protocol Pha 3](../../../docs/BENCHMARK_PHASE3_DESIGN.md): split/exposure,
  cách giữ kín held-out và gate. Gold Pha 2 cũ giữ nguyên receipt.

7 fixed-evidence probe, 1 rewrite probe, 8 end-to-end draft; 2 bài có history.
Các control dùng lại query có chủ đích, không tính là family độc lập. Pool bị
cắt thiếu căn cứ không biến full-corpus publish gold thành abstain. Probe không
được cộng vào mẫu số end-to-end. Bài wrong-citation mới có pool và yêu cầu
claim-to-source rubric; chưa có model output hay kết quả verifier.

Held-out **chưa author, chưa sealed**, chưa chỉ định custodian/author/reviewer.
12 family mục tiêu là budget thử workflow, không phải bộ 12 câu đã tồn tại.
Không sinh query held-out trong workspace/context dùng tuning. Còn numeric và
temporal suites cần gold riêng; 16 draft này không đóng Pha 3.

## Kiểm tra

```bash
.venv/bin/python -m evaluation.phase3_design verify
.venv/bin/python -m evaluation.reviewed_current_law_dataset verify
.venv/bin/python -m pytest tests/unit/test_phase3_design.py -q
```

Build là create-only; không có freeze/scoring command cho draft. Sau review cần
gold version riêng, không sửa manifest để giả approval. `screen_held_out` chỉ
chặn leakage phát hiện được từ metadata, không chứng minh access control,
review pháp lý hoặc model chưa thấy nguồn trong pretraining.

Bước tiếp theo: reviewer đọc 16 draft; author các suite biên còn thiếu và chỉ
định cách giữ held-out ngoài tuning workspace. Sau gold/exposure freeze mới
làm runner/replay. Chưa chạy C0–C4, chưa thay retrieval/model/index.
