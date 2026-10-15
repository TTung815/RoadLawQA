# Đánh giá và ground truth

Kết quả model nằm trong `outputs/evaluation/` ở workspace phát triển,
không được phát hành cùng Git.
`evaluation/datasets/` chứa câu hỏi, gold/citation và dữ liệu truy nguyên;
những thư mục mang tên draft không phải các lượt model cũ.

## Hai bộ cần dùng

| Bộ | Đáp án tham chiếu dễ đọc | Dữ liệu máy đọc |
| --- | --- | --- |
| 50 câu đã biết — nhãn v2 hiện hành | [REVIEWED.md](datasets/current_law_20260922_reviewed_v2/REVIEWED.md) | [cases.jsonl](datasets/current_law_20260922_reviewed_v2/cases.jsonl) |
| Development 54 đơn vị | [REVIEWED.md](datasets/current_law_20260922_development_reviewed_v1/REVIEWED.md) | [cases.jsonl](datasets/current_law_20260922_development_reviewed_v1/cases.jsonl) |

Gold của 50 gồm câu hỏi, đáp án tham chiếu, citation/evidence và điều kiện chấm.
Gold không phải đáp án model. Development gồm 12 QA, 7 coverage, 1 rewrite và
34 guard; không cộng thành 54 câu end-to-end. Held-out 9 được giữ ngoài repo.

Nhãn v2 được chủ dự án duyệt ngày 14/10/2026 sau review có AI hỗ trợ:
9 câu sửa nhãn/nội dung, 7 câu tinh chỉnh, 34 câu giữ nội dung. Có 45 câu
publish và 5 conditional; không có câu abstain nên không dùng riêng bộ này
đo khả năng từ chối. Câu hỏi 007/013/033 được làm rõ; không áp nhãn mới lên
kết quả cũ rồi coi đó là lượt chạy mới. Chi tiết ở
[README của bộ v2](datasets/current_law_20260922_reviewed_v2/README.md).

Runner dùng `--suite reviewed` cho v2; `--suite legacy` vẫn trỏ đúng bản v1
frozen. Bộ v1 và development 54 giữ nguyên. Kiểm tra offline:

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```

## Vì sao còn các thư mục cha?

Verifier tái dựng artifact từ đầu vào và so checksum, theo chuỗi:

```text
historical_50 → current_law_20260922 → current_law_20260922_reviewed_v1
                                       ├→ current_law_20260922_reviewed_v2
                                       ↓
                     current_law_20260922_phase3_design_v1
                                       ↓
                  current_law_20260922_development_draft_v1
                                       ↓
                 current_law_20260922_development_reviewed_v1
```

Xóa hoặc di chuyển đầu vào sẽ làm verify ground truth thất bại. Năm file
`docs/BENCHMARK_*.md`, các builder/schema và receipts cũng thuộc chuỗi checksum.
Giữ chúng nguyên vẹn. Thiết kế runtime hiện tại ở
[ARCHITECTURE.md](../docs/ARCHITECTURE.md); protocol ghi hợp đồng dữ liệu lịch sử.

## Công cụ

- `core_runner.py`: tạo plan, chạy bộ câu hỏi, checkpoint và lưu kết quả.
- `diagnose.py`: debug 1–15 câu đã biết, lưu đáp án/trace theo từng câu.
- `core_scoring.py`: gói review, đối chiếu nguồn và tổng hợp rubric hiện có.
- `module_scoring.py`: HitRate/Recall/MRR/nDCG trước–sau rerank cùng pool,
  coverage theo facet và latency; không gọi model hoặc truy xuất lại.
- `generation_scoring.py`: chấm lại đáp án đã lưu bằng LLM judge; Factual
  Precision/Recall/F1, Faithfulness, Answer Relevancy và Citation Precision/Recall.
  [Phương pháp và giới hạn](../docs/GENERATION_EVALUATION.md); có phí API riêng.
- `retrieval_ablation.py`: BM25, dense và hybrid theo alpha, trước/sau rerank,
  trên đường tìm kiếm thật của serving; không gọi LLM.
- `answer_judge.py`: rubric judge cho accuracy và hallucination trên đáp án cuối
  hoặc nháp đầu; nhãn suy ra bằng code, đo đồng thuận/kappa với nhãn người.
- `e2e_report.py`: gộp các lượt chạy, kết quả judge và metric từng bước thành
  một bảng so sánh cấu hình.
- `llm_preflight.py`: kiểm provider/schema trước lượt chạy thật.
- `*_dataset.py`, `phase3_design.py`, `current_law_snapshot.py`: build/verify
  dataset và corpus; các module có tên lịch sử vẫn là dependency cần dùng.
- `legacy_probe.py`, `snapshot.py`: helper BM25/ID và artifact dùng chung,
  không còn thực thi ứng dụng V1.

[Hướng dẫn chạy và chấm](../docs/EVALUATION_QUICKSTART.md).
