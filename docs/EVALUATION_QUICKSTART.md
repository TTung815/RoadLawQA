# Evaluation

Đánh giá tách riêng khả năng tìm nguồn (retrieval) và chất lượng câu trả lời
cuối (end-to-end). Bảng kết quả nằm trong [README](../README.md#evaluation).

## Benchmark

50 câu hỏi: 19 tình huống, 16 câu mức phạt, 15 câu định nghĩa/tra cứu; 45 câu
cần trả lời trực tiếp, 5 câu có điều kiện (trả lời theo nhánh hoặc hỏi rõ).
Mỗi câu có đáp án tham chiếu, các ý bắt buộc (facet), nguồn căn cứ và tiêu chí
trạng thái. Ground truth do chủ dự án duyệt và đã đối chiếu với nguyên văn
luật. [Cấu trúc dữ liệu](../evaluation/README.md).

## Metrics

**Retrieval** (không gọi LLM). Nguồn liên quan của một câu là các đơn vị
Điều/Khoản/Điểm chứa nguồn căn cứ của ý bắt buộc trong gold. Mỗi metric tính
cho từng câu rồi lấy trung bình trên 50 câu.

| Metric | Định nghĩa |
| --- | --- |
| Recall@k | Số nguồn liên quan nằm trong top k / tổng số nguồn liên quan |
| MRR@10 | 1 / thứ hạng của nguồn liên quan đầu tiên; 0 nếu không có trong top 10 |
| nDCG@10 | Chất lượng thứ tự top 10: nguồn liên quan xếp càng cao điểm càng lớn (relevance nhị phân, chuẩn hóa về [0, 1]) |
| Facet coverage | Tỷ lệ ý bắt buộc có đủ nguồn căn cứ trong evidence gửi cho LLM |

**End-to-end:**

| Metric | Định nghĩa |
| --- | --- |
| Accuracy | Đúng và đủ mọi ý bắt buộc, có nguồn hỗ trợ, đúng trạng thái (trả lời / hỏi rõ) |
| Hallucination | Có ít nhất một nhận định sai, hoặc trích nguồn không hỗ trợ nhận định ([Magesh et al., 2024](https://arxiv.org/abs/2405.20362)) |
| Faithfulness | Tỷ lệ nhận định được context hỗ trợ (theo [Ragas](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/)) |
| Citation P / R | Độ chính xác và độ phủ của citation theo từng nhận định (theo [ALCE](https://aclanthology.org/2023.emnlp-main.398/)) |
| Latency p50 / p95 | Thời gian mỗi câu, không gồm khởi tạo model |

## Scoring

**Accuracy, Hallucination:** LLM judge ([answer_judge.py](../evaluation/answer_judge.py))
chấm từng ý bắt buộc 0 / 0,5 / 1, liệt kê nhận định sai và citation không hỗ
trợ; nhãn cuối được suy ra bằng code, không do judge chọn. Trước khi dùng,
judge được kiểm trên 50 nhãn người: đồng thuận 92%, Cohen's κ = 0,71, chấm
khắt khe hơn người. Các câu judge đánh lỗi được rà tay và chủ dự án duyệt;
điểm thô của judge: Baseline 80%, Without reranker 82%, Full system 92%.

**Faithfulness, Citation P/R:** [generation_scoring.py](../evaluation/generation_scoring.py)
tách đáp án thành các nhận định rồi chấm từng nhận định với context và
citation. Hệ thống đầy đủ đo được 48/50 câu (2 lỗi của judge).

Khoảng tin cậy 95% (Wilson) của hệ thống đầy đủ: Accuracy 86,5–98,9%;
Hallucination 0/50 có cận trên 7,1%.

## Findings

Cấu hình: corpus cấu trúc v2, top 10, embedding CPU, reranker MPS, OpenAI
`gpt-6-luna` reasoning `medium`.

- **Hybrid search** tốt nhất khi chưa rerank: Recall@10 0,886 so với 0,781
  (BM25) và 0,820 (dense).
- **Reranker** tăng mọi cấu hình, rõ nhất ở MRR. Bỏ reranker thì p50 nhanh
  hơn 4,2s nhưng accuracy giảm 6 điểm, xuất hiện 2 hallucination do trích sai
  nguồn và p95 tăng lên 50s.
- **Tra dẫn chiếu** nâng độ phủ ý bắt buộc của evidence từ 0,893 (top 10) lên 0,98.
- **Sửa lỗi chọn nguồn và verifier** (Baseline → Full system): 88% → 96%. Bốn
  câu thiếu số điểm GPLX bị trừ nay lấy đủ nguồn; câu có trẻ em là hành khách
  không còn bị reranker đẩy nguồn đúng từ hạng 1 xuống 28.
- **Verifier:** ở cấu hình không reranker, verifier sửa 2 câu sai trạng thái
  và chặn 1 nháp sai trước khi công bố.

Hai câu chưa đạt: 007 đủ nội dung nhưng gắn trạng thái `partial` thừa; 016
thiếu nhắc quy tắc "chỉ được chở một người".

**Giới hạn:** judge cùng họ model với generator; ground truth không do chuyên
gia pháp luật duyệt; evaluator gọi thẳng pipeline RAG nên chưa đo router và
hội thoại nhiều lượt.

## Running

Các lệnh có `--live` gọi LLM và phát sinh phí. Mỗi lượt dùng thư mục mới trong
`outputs/evaluation/`; không ghi đè kết quả cũ.

Retrieval ablation (BM25 / dense / hybrid theo α, trước và sau rerank):

```bash
.venv/bin/python -m evaluation.retrieval_ablation --output outputs/evaluation/retrieval-ablation --alphas 0,0.25,0.5,0.75,1
```

Chạy end-to-end: tạo plan (khóa code, settings, dataset, index), kiểm provider,
chạy 50 câu.

```bash
.venv/bin/python -m evaluation.core_runner prepare --suite reviewed --output outputs/evaluation/run-v1/plan.json
.venv/bin/python -m evaluation.llm_preflight --plan outputs/evaluation/run-v1/plan.json --output outputs/evaluation/run-v1/preflight.json
.venv/bin/python -m evaluation.core_runner run --plan outputs/evaluation/run-v1/plan.json --preflight outputs/evaluation/run-v1/preflight.json --output outputs/evaluation/run-v1/run --live
```

Muốn tắt reranker: xuất settings bằng `core_runner settings --output settings.json`,
đặt `"rerank": false`, rồi `prepare ... --settings settings.json`.

Chấm và tổng hợp:

```bash
.venv/bin/python -m evaluation.answer_judge --run outputs/evaluation/run-v1/run --output outputs/evaluation/run-v1/judge --live
.venv/bin/python -m evaluation.generation_scoring --run outputs/evaluation/run-v1/run --output outputs/evaluation/run-v1/claims --live
.venv/bin/python -m evaluation.e2e_report --row "Full system" outputs/evaluation/run-v1/run outputs/evaluation/run-v1/judge --output outputs/evaluation/report
```

`answer_judge --which draft` chấm nháp đầu (trước verifier); `--reviews` đo
đồng thuận của judge với một file nhãn người. Debug 1–15 câu cụ thể bằng
`evaluation.diagnose`.
