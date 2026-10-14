# Development hoàn thiện về authoring/technical audit — draft v1

Cutoff 22/09/2026; lập 11/10/2026. Không phải scoring dataset được duyệt/freeze.

**Chủ dự án xem [REVIEW.md](REVIEW.md)**: chỉ 7 mục nội dung cần chốt, không
cần đọc code, các ký hiệu facet, từng batch hoặc duyệt lại 50 câu cũ.

- 4 tình huống mới sát biên 9/10/20/21 km/h, chỉ hỏi tiền, gold từ từng leaf và
  clause head; cùng family exposed của câu lịch sử 36/45.
- 2 conversation từ design v1, giữ nguyên câu trả lời nhưng cần chốt history
  có chỉ đúng tình huống và loại xe không.
- 1 mục quyết định dùng lại nội dung đã duyệt và giữ fail-closed cho fixtures
  còn lại; đầy đủ membership/hash ở review_groups.json, chưa có owner approval.

54 đơn vị: 16 design + 4 numeric + 34 publication-guard probes. Không phải 54
câu hỏi pháp luật độc lập: 12 end-to-end, 7 fixed-evidence, 1 rewrite, 34 guard.
Tất cả gold vẫn needs_review; technical audit của Codex không là review độc lập.

## Đối chiếu và kỹ thuật (tùy chọn)

- [EVIDENCE.md](EVIDENCE.md): full context, source spans và temporal metadata.
- [TECHNICAL.md](TECHNICAL.md), [technical_audit.json](technical_audit.json):
  kiểm tra dataset/provenance, không phải kết quả stage hoặc model.
- [cases.jsonl](cases.jsonl), [case.schema.json](case.schema.json): dữ liệu/schema.
- [numeric_labels.json](numeric_labels.json): bốn nhãn author mới, không copy
  mức tiền của nhánh 10–20 sang 9/21.
- [review_groups.json](review_groups.json): 7 nhóm, case IDs và content hashes.
- [exposure_inventory.json](exposure_inventory.json): nối inventory design với
  numeric/guard mới; vẫn cần semantic audit độc lập trước held-out.
- [manifest.json](manifest.json): binding design/reviewed/snapshot/tool/inputs.
- [Protocol bổ sung](../../../docs/BENCHMARK_DEVELOPMENT_DRAFT_V1.md).

Guard chỉ kiểm policy trên 10 locator blocked của frozen bundle: tại cutoff
và trước/đúng/sau 8 future anchors của 7 locator mixed/future. Không dự đoán
chế tài năm 2028/2029, không tự gỡ publication block hoặc positive-support
gate. Ba placeholder bãi bỏ chỉ probe tại cutoff, không giả nội dung luật cũ.

## Verify

```bash
.venv/bin/python -m evaluation.development_dataset verify
.venv/bin/python -m evaluation.phase3_design verify
.venv/bin/python -m evaluation.reviewed_current_law_dataset verify
.venv/bin/python -m pytest -q
```

Build create-only; chỉ có build/verify, **không có approve/freeze/scoring command**.
Sau owner review cần version riêng và review records/receipt; không sửa manifest
để giả approval. Parent design/draft/reviewed và frozen builders/protocols giữ
nguyên checksum. Chưa runner/C0–C4, chưa thay production hoặc ingest thêm nguồn.

Held-out vẫn blueprint, chưa có query/gold/custodian/sealed storage. Cần bước
bố trí author/review/custody độc lập; development hoàn thiện không đóng gate Pha 3.
