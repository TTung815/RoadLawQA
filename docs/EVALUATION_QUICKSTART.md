# Đánh giá RoadLawQA

Đánh giá tách khả năng tìm nguồn, chất lượng trả lời và chi phí vận hành.
Nguồn xuất hiện trong top-k hoặc trạng thái `answered` không tự chứng minh
đáp án đúng. Kết quả phụ thuộc phiên bản code, corpus, provider và cấu hình.

## Dataset và phạm vi đo

| Bộ | Nội dung | Mục đích |
| --- | --- | --- |
| Reviewed 50 | 50 câu, đáp án tham chiếu, ý bắt buộc, nguồn căn cứ và điều kiện chấm | Đánh giá retrieval và end-to-end |

Suite `reviewed` trỏ tới bộ v2 hiện hành. [Cấu trúc dữ liệu đánh giá](../evaluation/README.md).

Evaluator pháp luật chạy `AnswerService`/`LeanRetrievalService`, không qua
`ChatService`/`ConversationRouter`. Nó có contextualization khi có lịch sử,
nhưng không đo routing và expansion trong chatbot. Muốn đánh giá trải nghiệm
hội thoại, phải kiểm riêng API `/api/v1/answer`, bao gồm cả lịch sử và intent.
Preflight hiện kiểm provider và năm schema RAG; chưa kiểm schema router.

## Kết quả hiện hành — 15/10/2026

Bảng retrieval và end-to-end nằm ở [README](../README.md#đánh-giá-trên-benchmark-50-câu-15102026).
Các lượt dùng commit `0ab680e`, structured v2, top 10, alpha 0.5, embedding CPU,
reranker MPS batch 4, OpenAI `gpt-6-luna` medium; plan khóa hash code, preflight
6/6. Artifact giữ local:

| Thư mục `outputs/evaluation/` | Nội dung |
| --- | --- |
| `groundtruth-audit-20261015-v1/` | Rà lại 50 đáp án tham chiếu với nguyên văn nguồn |
| `retrieval-ablation-20261015-v1/` | BM25 / dense / hybrid α 0–1, trước và sau rerank, không gọi LLM |
| `judge-validation-20261015-v1/` | Rubric judge chấm lại 50 đáp án 14/10: đồng thuận 92%, kappa 0,71 |
| `e2e-full-20261015-v1/`, `e2e-norerank-20261015-v1/` | Hai lượt 50 câu, judge đáp án cuối và nháp đầu, metric claim-level |
| `e2e-ablation-20261015-v1/` | Bảng tổng hợp, rà tay các câu judge đánh lỗi và quyết định duyệt |
| `rag-modules-v2-20261014-v1/` | Lượt trước sửa lỗi, nhãn người 44/50 đã duyệt |

Judge dùng cùng họ model với generator và chấm khắt khe hơn người; chấm lại
cùng nội dung đổi nhãn khoảng 5%. Vì vậy chênh 1–2 câu giữa hai cấu hình chưa
đủ kết luận. Số chính trong README là nhãn sau rà tay đã duyệt; điểm thô của
judge được ghi kèm.

## Ablation và chấm end-to-end

Retrieval ablation, không gọi LLM:

```bash
.venv/bin/python -m evaluation.retrieval_ablation --output outputs/evaluation/retrieval-ablation-next --alphas 0,0.25,0.5,0.75,1
```

Plan không reranker: sao settings bằng `core_runner settings`, đặt
`"rerank": false`, rồi `prepare`/preflight/run như một lượt thường. Chấm bằng
rubric judge (có gọi LLM), kiểm judge với nhãn người và gộp bảng:

```bash
.venv/bin/python -m evaluation.answer_judge --run outputs/evaluation/next-run-v1/run --output outputs/evaluation/next-run-v1/judge-final --which final --live
.venv/bin/python -m evaluation.answer_judge --run outputs/evaluation/next-run-v1/run --output outputs/evaluation/next-run-v1/judge-draft --which draft --live
.venv/bin/python -m evaluation.answer_judge --run outputs/evaluation/rag-modules-v2-20261014-v1/run --output outputs/evaluation/judge-check --reviews outputs/evaluation/rag-modules-v2-20261014-v1/review/reviews_ai.jsonl --live
.venv/bin/python -m evaluation.e2e_report --row "Đầy đủ" outputs/evaluation/next-run-v1/run outputs/evaluation/next-run-v1/judge-final --output outputs/evaluation/next-report
```

Judge chấm từng ý bắt buộc 0 / 0,5 / 1, trích nguyên văn nhận định sai và chỉ
ra claim có citation không hỗ trợ; code suy ra nhãn `correct`, `status_issue`,
`incomplete`, `not_answered` hoặc `hallucinated`. `--which draft` chấm nháp đầu
trước verifier; khi lượt chạy không có lần sửa nào, nháp và đáp án cuối trùng
nhau nên chênh lệch chỉ phản ánh dao động của judge.

## Các phép đo cần phân biệt

Để chấm các metric generation riêng trên đáp án đã lưu, xem
[GENERATION_EVALUATION.md](GENERATION_EVALUATION.md). Scorer này có lời gọi
LLM judge và kết quả riêng; accuracy theo rubric không phải Factual F1
hoặc Faithfulness. Không cần chạy lại retrieval/generation để chấm bổ sung.

| Thành phần | Đã có | Phép đo mở rộng phù hợp |
| --- | --- | --- |
| Retrieval | Recall@1,5,10, MRR, nDCG; ablation BM25/dense/hybrid; coverage và latency | Nhãn relevance rộng hơn các nguồn tham chiếu gold |
| Reranker | Trước–sau trên cùng pool; ablation end-to-end có/không rerank | Nhiều câu hơn để kiểm định có ý nghĩa thống kê |
| Generation | Accuracy, hallucination (rubric judge đã kiểm với nhãn người); Faithfulness, Citation P/R, Factual F1 | Judge khác họ model để giảm thiên lệch |
| Verification | Pass/fail, repair, nháp đầu so với đáp án cuối | Bộ nháp cài lỗi để đo tỷ lệ phát hiện |
| Hội thoại | Probe intent, follow-up và expansion | Accuracy intent, bảo toàn dữ kiện và thành công nhiều lượt |

Cột cuối là hướng đo tiếp, chưa có kết quả. Không tái sử dụng bảng
Recall/MRR/accuracy của ứng dụng cũ để mô tả
index mới. Scorer tự động hiện hỗ trợ các kiểm kỹ thuật cùng rubric facet/flags;
review bốn nhãn gọn cần lưu riêng, không đổi tên thành điểm strict của scorer.

Trace mới có sự kiện `retrieval_ranking`: thứ hạng từng view native, pool ứng
viên sau xen kẽ/khử trùng và thêm locator, thứ hạng reranker trên toàn bộ pool,
và top-k được chọn. So sánh reranker trước–sau trên cùng pool, ghi rõ thứ tự
trước là thứ tự hợp nhất thực tế, không phải một bảng điểm hybrid chung.
Nhãn gold dùng leaf frozen; cần ánh xạ qua `source_processed_ids` của chunk
cấu trúc và phân biệt nguồn cần đủ theo facet với nguồn hỗ trợ thay thế.
Recall theo nguồn tham chiếu không đo mọi nguồn có thể đúng. MRR/nDCG dùng
nhãn nhị phân từ gold chỉ là proxy nếu chưa review relevance từng ứng viên;
không coi mọi chunk ngoài gold là chắc chắn không liên quan. Báo cáo riêng
top-k chính và evidence sau tra dẫn chiếu, không gộp chúng thành Recall@10.

`evaluation.module_scoring` chấm trace của suite `reviewed`, corpus structured:
HitRate/Recall/MRR/nDCG nhị phân tại K=1,5,10, coverage facet, candidate recall,
coverage sau tra dẫn chiếu và latency từng bước. Đây là so thứ hạng trước/sau
trên cùng pool, chưa phải ablation câu trả lời khi tắt reranker. Nguồn chỉ phục
vụ facet bổ sung không vào tập gold cần truy xuất. Recall tính hợp các nguồn
tham chiếu; coverage facet giữ điều kiện all/any và nhóm thay thế. Bảng luôn
ghi số câu có trace; trace thiếu là N/A. Verifier pass/repair là thống kê vận
hành, chưa phải tỷ lệ phát hiện sai được gán nhãn độc lập.

## Chuẩn bị một lượt RAG mới

Cần môi trường và artifact theo [SETUP.md](SETUP.md). Tạo thư mục mới cho mỗi
code/settings; không ghi đè kết quả cũ. Các lệnh preflight và `--live` gọi
provider thật, có thể phát sinh chi phí theo tài khoản đang cấu hình.

```bash
.venv/bin/python -m evaluation.core_runner prepare --suite reviewed --output outputs/evaluation/next-run-v1/plan.json
.venv/bin/python -m evaluation.llm_preflight --plan outputs/evaluation/next-run-v1/plan.json --output outputs/evaluation/next-run-v1/preflight.json
```

Plan khóa code/settings, dataset, corpus và index receipt; không chứa key.
Preflight kiểm gọi text và schema. Nếu đổi code/model/settings, tạo plan mới
thay vì dùng receipt cũ. Khi thiếu bảng giá đã xác minh, chi phí ghi null.

Kiểm riêng retrieval, không gọi LLM/router: dùng `evaluation.retrieval_ablation`
ở mục "Ablation và chấm end-to-end".

## Chẩn đoán và chạy bộ câu hỏi

Chẩn đoán 1–15 câu đã biết; công cụ không cho mở held-out:

```bash
.venv/bin/python -m evaluation.diagnose --plan outputs/evaluation/next-run-v1/plan.json --preflight outputs/evaluation/next-run-v1/preflight.json --case current_law_023 --case current_law_029 --output outputs/evaluation/next-run-v1/diagnostics --live
```

Chạy đủ bộ và tạo gói review:

```bash
.venv/bin/python -m evaluation.core_runner run --plan outputs/evaluation/next-run-v1/plan.json --preflight outputs/evaluation/next-run-v1/preflight.json --output outputs/evaluation/next-run-v1/run --live
.venv/bin/python -m evaluation.core_scoring review-packet --run outputs/evaluation/next-run-v1/run --output outputs/evaluation/next-run-v1/review
```

Runner lưu checkpoint từng câu; một lượt gián đoạn chưa là run hoàn chỉnh.
Đọc `output.answer.text`, `output.limitations`, `output.follow_up_questions`,
`output.retrieval`, `output.verification` và lỗi theo stage. Diagnostics có
thể chứa nháp chưa kiểm chứng; không dùng nháp bị chặn làm đáp án người dùng.

Để dùng scorer facet hiện có, điền `reviews.jsonl` từ template trong gói
review, giữ result hash, reviewer và các facet keys, rồi chạy:

```bash
.venv/bin/python -m evaluation.core_scoring score --run outputs/evaluation/next-run-v1/run --reviews outputs/evaluation/next-run-v1/review/reviews.jsonl --output outputs/evaluation/next-run-v1/report
.venv/bin/python -m evaluation.module_scoring --run outputs/evaluation/next-run-v1/run --output outputs/evaluation/next-run-v1/modules
```

Không có semantic reviews thì số liệu kỹ thuật chưa là điểm đúng nội dung.
Với nhãn v2, điền thêm `response_appropriate` theo tiêu chí trạng thái trong
gói review. `null` là chưa chấm; chỉ chọn true khi trả lời theo điều kiện,
hỏi rõ hoặc trả lời một phần phù hợp yêu cầu và dữ kiện của câu. Trạng thái
được cho phép không tự tạo điểm pass: vẫn cần đủ mọi facet bắt buộc, citation
đúng và được nguồn hỗ trợ, công bố an toàn. Facet bổ sung không tính vào mẫu
số completeness, nhưng nếu model nói thêm sai thì vẫn chấm sai nội dung.
Rubric này áp dụng cho suite `reviewed`.
Giữ exception/timeout trong tổng số câu; không loại bỏ trường hợp lỗi để tăng
điểm. Chấm tương đương về nghĩa, đồng thời kiểm chủ thể, điều kiện, con số,
hiệu lực và nguồn hỗ trợ. Nếu gold có vấn đề, ghi nhận riêng thay vì sửa bản frozen.
