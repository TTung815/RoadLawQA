# Evaluation Data and Tools

Metric, phương pháp chấm và lệnh chạy: [EVALUATION_QUICKSTART.md](../docs/EVALUATION_QUICKSTART.md).
Kết quả các lượt chạy lưu trong `outputs/evaluation/` (không đưa vào Git).

## Benchmark

| Bộ | Bản dễ đọc | Dữ liệu máy đọc |
| --- | --- | --- |
| 50 câu, nhãn v2 | [REVIEWED.md](datasets/current_law_20260922_reviewed_v2/REVIEWED.md) | [cases.jsonl](datasets/current_law_20260922_reviewed_v2/cases.jsonl) |

Mỗi câu gồm câu hỏi, đáp án tham chiếu, các ý bắt buộc (facet), nhóm nguồn
căn cứ và tiêu chí trạng thái trả lời. [Chi tiết bộ v2](datasets/current_law_20260922_reviewed_v2/README.md).

Kiểm manifest, hash từng câu và nguồn khớp corpus:

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```

## Tools

| Module | Vai trò |
| --- | --- |
| `core_runner.py` | Tạo plan khóa code/settings, chạy bộ câu hỏi, checkpoint |
| `llm_preflight.py` | Kiểm provider và schema trước lượt chạy thật |
| `diagnose.py` | Debug 1–15 câu, lưu đáp án và trace từng câu |
| `retrieval_ablation.py` | BM25 / dense / hybrid theo α, trước và sau rerank; không gọi LLM |
| `module_scoring.py` | Recall/MRR/nDCG trước–sau rerank, độ phủ facet, latency từng bước |
| `answer_judge.py` | LLM judge cho Accuracy và Hallucination; đo đồng thuận với nhãn người |
| `generation_scoring.py` | Faithfulness, Citation P/R theo từng nhận định (tính thêm Factual P/R/F1, Answer Relevancy nhưng không dùng trong báo cáo) |
| `e2e_report.py` | Gộp các lượt chạy và kết quả judge thành bảng so sánh |
| `core_scoring.py` | Gói review cho người chấm và tổng hợp nhãn |
| `revised_current_law_dataset.py`, `gold_support.py` | Nạp, kiểm benchmark và nguồn gold |
| `current_law_snapshot.py`, `legacy_probe.py`, `snapshot.py` | Kiểm snapshot corpus gốc mà gold dựa vào |
