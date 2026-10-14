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
Tên suite `reviewed` trỏ tới **reviewed 50 v2 hiện hành**; `legacy` giữ nhãn
reviewed v1 cho lịch sử, không chạy ứng dụng V1. Các bộ draft/history và năm protocol là dependency checksum, không
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

## RAG 50 câu với nhãn v2 — 14/10/2026

Lượt `rag-modules-v2-20261014-v1` chạy đủ 50 câu, không lỗi kỹ thuật,
structured v2/top 10/alpha 0.5, embedding CPU, reranker MPS batch 4,
OpenAI `gpt-6-luna` medium. Plan khóa 63 hash code; không đổi cấu hình trong
lượt chạy. Đây là bộ đã biết, chưa phải held-out hoặc toàn luồng chatbot.

| Metric @10, trung bình 50 câu | Trước rerank | Sau rerank |
| --- | ---: | ---: |
| HitRate | 98,00% | 98,00% |
| Recall nguồn tham chiếu | 88,63% | 89,37% |
| MRR | 0,7992 | 0,8740 |
| nDCG nhị phân | 0,7724 | 0,8291 |

Đây là so thứ hạng trên cùng pool, không phải chạy end-to-end khi tắt reranker.
Candidate recall trung bình 93,93%; coverage facet sau tra dẫn chiếu 92,00%
theo trung bình từng câu, hoặc 75/82 facet (91,46%) khi gộp các facet.

Review **có AI hỗ trợ, chủ dự án đã duyệt ngày 15/10/2026**: 44/50 đạt đủ ý và trạng thái;
1 câu đủ nội dung nhưng trạng thái quá thận trọng (007); 4 thiếu ý (005/008/020/038);
1 chưa trả lời (019). Điểm facet 77/82. Có 77/77 lượt citation hợp lệ về ID/text;
review nội dung thấy citation hỗ trợ ở 49/49 câu có claims. Các tỷ lệ citation
này không đo độ đầy đủ đáp án hoặc chứng minh accuracy trên câu hỏi mới.

Latency mean 14,99s, median 12,95s, p95 28,82s; không gồm khởi tạo runtime.
Generation mean 6,23s, rerank 4,52s, verification 4,04s. Có 102 logical LLM
calls trong batch, 1 lần sửa nháp; 6 calls preflight tính riêng. Verifier cuối
cùng passed cả 50 nhưng không đồng nghĩa cả 50 đáp án đạt đủ yêu cầu.

Bốn câu thiếu điểm phạt không có nguồn cần thiết trong pool; câu 019 có nguồn
đúng ở hạng 1 trước rerank nhưng xuống hạng 28. Vì vậy kết quả reranker cải
thiện trung bình không bảo đảm cải thiện mọi câu. Artifact và phiếu duyệt
được giữ local tại `outputs/evaluation/rag-modules-v2-20261014-v1/`.

## Các phép đo cần phân biệt

Để chấm các metric generation riêng trên đáp án đã lưu, xem
[GENERATION_EVALUATION.md](GENERATION_EVALUATION.md). Scorer này có lời gọi
LLM judge và kết quả riêng; điểm rubric 44/50 ở trên không phải Factual F1
hoặc Faithfulness. Không cần chạy lại retrieval/generation để chấm bổ sung.

| Thành phần | Đã có | Phép đo mở rộng phù hợp |
| --- | --- | --- |
| Retrieval | HitRate/Recall@1,5,10, coverage và latency trên reviewed v2 | Nhãn relevance rộng hơn các nguồn tham chiếu gold |
| Reranker | MRR/nDCG nhị phân trước–sau trên cùng pool | Ablation end-to-end để đo tác động tới đáp án |
| Generation | Factual P/R/F1, Faithfulness, Answer Relevancy, Citation P/R bằng LLM judge; review rubric riêng | Owner duyệt các judgment và kiểm trên held-out sau chốt cấu hình |
| Verification | Pass/fail, repair và latency | Độ chính xác phát hiện lỗi trên bộ nhãn độc lập |
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
.venv/bin/python -m evaluation.module_scoring --run outputs/evaluation/next-run-v1/run --output outputs/evaluation/next-run-v1/modules
```

Không có semantic reviews thì số liệu kỹ thuật chưa là điểm đúng nội dung.
Với nhãn v2, điền thêm `response_appropriate` theo tiêu chí trạng thái trong
gói review. `null` là chưa chấm; chỉ chọn true khi trả lời theo điều kiện,
hỏi rõ hoặc trả lời một phần phù hợp yêu cầu và dữ kiện của câu. Trạng thái
được cho phép không tự tạo điểm pass: vẫn cần đủ mọi facet bắt buộc, citation
đúng và được nguồn hỗ trợ, công bố an toàn. Facet bổ sung không tính vào mẫu
số completeness, nhưng nếu model nói thêm sai thì vẫn chấm sai nội dung.
Rubric này chỉ áp dụng suite `reviewed`, không đổi điểm lịch sử của v1.
Giữ exception/timeout trong tổng số câu; không loại bỏ trường hợp lỗi để tăng
điểm. Chấm tương đương về nghĩa, đồng thời kiểm chủ thể, điều kiện, con số,
hiệu lực và nguồn hỗ trợ. Nếu gold có vấn đề, ghi nhận riêng thay vì sửa bản frozen.

Development dùng `prepare --suite development`. Held-out chỉ dùng sau khi
chốt cấu hình; runner nhận file câu hỏi riêng, scorer mới nhận gold. Xem
`python -m evaluation.core_runner prepare --help` để biết tham số nhập bộ riêng.
