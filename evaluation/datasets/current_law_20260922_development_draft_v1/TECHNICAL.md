# Technical/source audit — development draft v1

Các check dưới đây do Codex thực hiện; **không là review pháp lý độc lập hoặc model pass**.

54 đơn vị: 16 design, 4 numeric, 34 guard; tất cả needs_review.
Modes: {'fixed_evidence': 7, 'rewrite_probe': 1, 'end_to_end': 12, 'publication_guard_probe': 34}; guard 10 locator, 8 mốc tương lai.

- PASS (dataset/provenance): frozen source/snapshot/gold/design integrity
- PASS (dataset/provenance): typed draft-only schema and provenance
- PASS (dataset/provenance): numeric source interval/query/clause-head money
- PASS (dataset/provenance): stable evidence reference and full context hashes
- PASS (dataset/provenance): blocked context-only guard and registered temporal offsets
- PASS (dataset/provenance): replay pool/facet consistency
- PASS (dataset/provenance): review group exact membership/hash

0 model runs, 0 production writes; chưa runner/C0–C4, chưa held-out.
Xem REVIEW.md cho 7 quyết định nội dung; owner không phải audit pool/code.

