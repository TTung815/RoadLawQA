# Đánh giá RoadLawQA

Đánh giá tách khả năng tìm nguồn, chất lượng trả lời và chi phí vận hành.
Nguồn xuất hiện trong top-k hoặc trạng thái `answered` không tự chứng minh
đáp án đúng. Kết quả phụ thuộc phiên bản code, corpus, provider và cấu hình.

## Dataset và phạm vi đo

| Bộ | Nội dung | Mục đích |
| --- | --- | --- |
| Reviewed 50 | 50 câu đã biết, gold/citation và điều kiện chấm | Đánh giá RAG trên nguồn đã review |
| Development 54 | 12 QA, 7 coverage, 1 rewrite và 34 guard | Kiểm từng hành vi; không phải 54 câu end-to-end |
| Held-out 9 | Giữ riêng ngoài workspace | Chỉ mở sau khi chốt cấu hình, không dùng tuning |

[Bản đồ dataset và provenance](../evaluation/README.md).
Tên suite `legacy` của runner trỏ tới **reviewed 50 hiện hành**, không chạy ứng
dụng V1. Các bộ draft/history và năm protocol là dependency checksum, không
xóa chỉ vì tên có chữ draft hoặc phiên bản cũ.

Evaluator pháp luật chạy `AnswerService`/`LeanRetrievalService`, không qua
`ChatService`/`ConversationRouter`. Nó có contextualization khi có lịch sử,
nhưng không đo routing và expansion trong chatbot. Muốn đánh giá trải nghiệm
hội thoại, phải kiểm riêng API `/api/v1/answer`, bao gồm cả lịch sử và intent.
Preflight hiện kiểm provider và năm schema RAG; chưa kiểm schema router.

## Kết quả đã xác minh cho code e38f086

Đo trên workspace phát triển ngày 14/10/2026, MacBook M3 Pro; embedding CPU,
reranker MPS, OpenAI `gpt-6-luna`, reasoning `medium`.

| Kiểm tra | Kết quả |
| --- | --- |
| Offline suite | 534 passed, 9 integration deselected |
| Integration riêng | 9 passed trên Weaviate/model thật |
| Router probe | 7 tin nhắn, kiểm phạm vi/phủ định/khoảng tuổi/khoảng tốc độ |
| Chatbot probe | 6 lượt answered và verification passed, 1 lượt repair |
| Calls | 27 logical calls: 7 router-only + 20 cho sáu lượt chatbot |
| Latency chatbot | Mean 19,62s; median 16,73s; min–max 10,96–36,86s |
| Đối chiếu artifact | 61 hash plan, 43 lượt nguồn và 19 lượt citation của claims |

Sáu lượt gồm câu tín hiệu giao thông chung và hỏi tiếp loại xe, quai mũ bảo
hiểm, nhiều hành vi đồng thời, tốc độ khi vượt xe và tuổi chịu xử phạt.
Đây là các câu đã dùng để chẩn đoán; review có AI hỗ trợ, chưa phải đánh giá
độc lập. Thời gian không gồm khởi tạo model/database. Verifier có thể sai.
Không diễn giải kết quả thành accuracy 100% hoặc cam kết latency dưới 20 giây.

Artifact gốc: `outputs/diagnostics/query-expansion-20261014-v2/` chứa plan,
receipt, answer/trace từng câu và validation. Các file này đang giữ local,
không phải link tải công khai. Lượt full-50 cũ có trước pipeline/index/router
hiện tại; chưa có điểm full-50 cho toàn chatbot mới.

## Các phép đo cần phân biệt

| Thành phần | Đã có | Phép đo mở rộng phù hợp |
| --- | --- | --- |
| Retrieval | Kiểm nguồn tham chiếu, eligibility và latency | Recall@k/HitRate@k trên nhãn nguồn của corpus hiện hành |
| Reranker | Regression nguồn sau rerank, timer và device | MRR/nDCG khi có nhãn relevance đủ rõ; so cùng candidate pool |
| Generation/verification | Review claims/citation, completeness, trạng thái và repair | Đúng / thiếu ý / sai / chưa trả lời, kèm kiểm điều kiện áp dụng |
| Hội thoại | Probe intent, follow-up và expansion | Accuracy intent, bảo toàn dữ kiện và thành công nhiều lượt |

Cột cuối là hướng đo, không phải các chỉ số đã được tính đầy đủ cho phiên bản
hiện tại. Không tái sử dụng bảng Recall/MRR/accuracy của ứng dụng cũ để mô tả
index mới. Scorer tự động hiện hỗ trợ các kiểm kỹ thuật cùng rubric facet/flags;
review bốn nhãn gọn cần lưu riêng, không đổi tên thành điểm strict của scorer.

## Chuẩn bị một lượt RAG mới

Cần môi trường và artifact theo [SETUP.md](SETUP.md). Tạo thư mục mới cho mỗi
code/settings; không ghi đè kết quả cũ. Các lệnh preflight và `--live` gọi
provider thật, có thể phát sinh chi phí theo tài khoản đang cấu hình.

```bash
.venv/bin/python -m evaluation.core_runner prepare --suite legacy --output outputs/evaluation/next-run-v1/plan.json
.venv/bin/python -m evaluation.llm_preflight --plan outputs/evaluation/next-run-v1/plan.json --output outputs/evaluation/next-run-v1/preflight.json
```

Plan khóa code/settings, dataset, corpus và index receipt; không chứa key.
Preflight kiểm gọi text và schema. Nếu đổi code/model/settings, tạo plan mới
thay vì dùng receipt cũ. Khi thiếu bảng giá đã xác minh, chi phí ghi null.

Kiểm riêng retrieval, không gọi LLM/router:

```bash
.venv/bin/python -m evaluation.retrieval_demo --output outputs/evaluation/retrieval-demo-next
```

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
```

Không có semantic reviews thì số liệu kỹ thuật chưa là điểm đúng nội dung.
Giữ exception/timeout trong tổng số câu; không loại bỏ trường hợp lỗi để tăng
điểm. Chấm tương đương về nghĩa, đồng thời kiểm chủ thể, điều kiện, con số,
hiệu lực và nguồn hỗ trợ. Nếu gold có vấn đề, ghi nhận riêng thay vì sửa bản frozen.

Development dùng `prepare --suite development`. Held-out chỉ dùng sau khi
chốt cấu hình; runner nhận file câu hỏi riêng, scorer mới nhận gold. Xem
`python -m evaluation.core_runner prepare --help` để biết tham số nhập bộ riêng.
