# Đánh giá và ground truth

Kết quả model nằm trong `outputs/evaluation/` ở workspace phát triển,
không được phát hành cùng Git.

## Benchmark

| Bộ | Đáp án tham chiếu dễ đọc | Dữ liệu máy đọc |
| --- | --- | --- |
| 50 câu — nhãn v2 | [REVIEWED.md](datasets/current_law_20260922_reviewed_v2/REVIEWED.md) | [cases.jsonl](datasets/current_law_20260922_reviewed_v2/cases.jsonl) |

Mỗi câu gồm câu hỏi, đáp án tham chiếu, các ý bắt buộc (facet), nhóm nguồn
căn cứ và tiêu chí trạng thái trả lời. Gold không phải đáp án model. Có 19 câu
tình huống, 16 câu mức phạt và 15 câu định nghĩa/tra cứu; 45 câu cần trả lời
trực tiếp và 5 câu có điều kiện (được giữ nhánh hoặc hỏi rõ). Chi tiết ở
[README của bộ v2](datasets/current_law_20260922_reviewed_v2/README.md).

Kiểm tra offline (manifest, hash từng case so với quyết định duyệt, nguồn khớp
corpus và không thuộc nhóm bị chặn):

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```

## Công cụ

- `core_runner.py`: tạo plan, chạy bộ câu hỏi, checkpoint và lưu kết quả.
- `diagnose.py`: debug 1–15 câu đã biết, lưu đáp án/trace theo từng câu.
- `core_scoring.py`: gói review, đối chiếu nguồn và tổng hợp rubric.
- `module_scoring.py`: Recall/MRR/nDCG trước–sau rerank cùng pool,
  coverage theo facet và latency; không gọi model hoặc truy xuất lại.
- `retrieval_ablation.py`: BM25, dense và hybrid theo alpha, trước/sau rerank,
  trên đường tìm kiếm thật của serving; không gọi LLM.
- `answer_judge.py`: rubric judge cho accuracy và hallucination trên đáp án cuối
  hoặc nháp đầu; nhãn suy ra bằng code, đo đồng thuận/kappa với nhãn người.
- `generation_scoring.py`: Factual Precision/Recall/F1, Faithfulness và Citation
  Precision/Recall theo từng nhận định.
  [Phương pháp và giới hạn](../docs/GENERATION_EVALUATION.md); có phí API riêng.
- `e2e_report.py`: gộp các lượt chạy, kết quả judge và metric từng bước thành
  một bảng so sánh cấu hình.
- `llm_preflight.py`: kiểm provider/schema trước lượt chạy thật.
- `revised_current_law_dataset.py`, `gold_support.py`: nạp/kiểm benchmark và
  các hàm dùng chung cho nguồn gold.
- `current_law_snapshot.py`, `legacy_probe.py`, `snapshot.py`: kiểm snapshot
  corpus frozen và các helper ID/artifact dùng chung.

[Hướng dẫn chạy và chấm](../docs/EVALUATION_QUICKSTART.md).
