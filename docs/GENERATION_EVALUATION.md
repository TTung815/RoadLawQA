# Đánh giá generation từ kết quả đã lưu

`evaluation.generation_scoring` chấm đáp án cuối trên run reviewed v2, không
chạy lại retrieval/generation và không sửa câu trả lời, gold hoặc review cũ.
Phương pháp `claim-metrics-v1` là triển khai trong repository dựa trên công
thức Ragas và ALCE; **không phải chạy package Ragas hoặc tái lập nguyên bản
ALCE**. Prompt, schema, model, revision embedding và đầu vào được khóa hash.

## Metric và mẫu số

Các metric chính báo macro mean theo câu, kèm số câu đo được. Giá trị N/A
không biến thành 0 hoặc 1. Lỗi giám khảo ghi riêng, không gọi là đáp án sai.

| Metric | Định nghĩa |
| --- | --- |
| Factual Precision | TP/(TP+FP): số assertion của đáp án được reference hỗ trợ / số assertion đáp án |
| Factual Recall | TP/(TP+FN): FN là số assertion reference chưa được đáp án hỗ trợ |
| Factual F1 | 2TP/(2TP+FP+FN), dùng count formulation của Ragas |
| Faithfulness | Assertion được context hỗ trợ / toàn bộ assertion đáp án |
| Answer Relevancy | Trung bình cosine giữa query gốc và ba câu hỏi suy ngược từ đáp án |
| Citation Recall | Assertion được hợp các nguồn trích tại segment cha hỗ trợ / toàn bộ assertion |
| Citation Precision | Citation hữu ích / toàn bộ citation; chỉ công nhận khi mọi assertion trong segment cha có đủ citation support |

Factual Recall dùng TP đếm phía response, FN phía reference như công thức
Ragas; do cách chia assertion có thể khác nhau, không đồng nhất nó với tỷ lệ
facet của gold đã được đáp ứng. Lưu cả số reference assertions được bao phủ.
Citation Recall dùng atomic assertions, Citation Precision dùng citation–segment
pairs với joint-support gate theo ALCE; đây là biến thể được ghi rõ, không
so trực tiếp điểm với benchmark ALCE khác đơn vị chia câu.

Không có substantive claims: Precision/Faithfulness/Citation là N/A;
Factual Recall/F1/Relevancy bằng 0 vì bộ hiện tại yêu cầu một đáp án có nội
dung. Chính sách này không dùng đánh giá bộ có câu hỏi phải từ chối.
Cosine có miền [-1,1], không nhân 100 rồi gọi là accuracy.

## Giám khảo và cách tách thông tin

1. Decomposition chỉ thấy các đoạn đáp án, limitations và follow-up, không
   thấy query gốc/gold/context. Tách assertion và tạo ba câu hỏi suy ngược
   trong cùng lượt. Mỗi assertion giữ quote nguyên văn và segment cha.
2. Factual judge thấy query, reference và assertion đáp án; tách reference,
   chấm entailment hai chiều. Không thấy context hoặc review trước.
3. Grounding judge thấy query, assertion và context/citation; không thấy gold
   hoặc kết quả factual. Chấm hỗ trợ context/citation và limitations riêng.
4. Tính cosine bằng embedding multilingual đang có, CPU và revision khóa theo
   run gốc. Không cần database/reranker để chấm lại.

Giữ provider/model/reasoning của run gốc. Cùng model với generator có thể
có thiên lệch tự đánh giá; kết quả là LLM-judge và chờ người duyệt. Không dùng
verifier passed làm nhãn đúng. Được áp dụng quy tắc vào dữ kiện câu hỏi và
chấp nhận paraphrase, nhưng không bổ sung luật từ trí nhớ. Dữ kiện do người
hỏi nêu được coi là giả định của tình huống: nguồn luật hỗ trợ quy tắc áp
dụng và phép suy luận, không chứng thực sự kiện ngoài đời. Ví dụ, phép trừ
tốc độ 92−80=12 dùng dữ kiện query; không yêu cầu văn bản luật phải chứa
hai số 92 và 80. Đây là faithfulness có điều kiện theo query.

Factual metric chỉ so reference nên có thể phạt thông tin bổ sung đúng nhưng
không nằm trong reference; xem lý do và Faithfulness trước khi kết luận lỗi
pháp lý. Toàn bộ reference được tách, nên có thể nghiêm hơn rubric facet bắt
buộc. Limitations/hỏi rõ được audit riêng, không trộn các phát biểu về thiếu
nguồn vào assertion pháp luật. Trạng thái phù hợp vẫn do rubric end-to-end
đo riêng. Relevancy dùng ba reverse questions chung một lượt, không phải ba
lần lấy mẫu độc lập và không dùng noncommittal multiplier; trường hợp đáp án
rỗng được xử lý riêng. Điểm cao không chứng minh đúng luật hoặc trả lời đủ.

## Chạy

```bash
.venv/bin/python -m evaluation.generation_scoring --run outputs/evaluation/rag-modules-v2-20261014-v1/run --output outputs/evaluation/generation-metrics-v1 --live
```

Có thêm lời gọi LLM để chấm. Preflight ba schema trước batch; tối đa hai
attempt mỗi stage (gồm thử lại khi validation/network thất bại), concurrency
hai câu, provider riêng từng câu để không trộn usage. Checkpoint theo từng
stage; `--resume` chỉ tái dùng khi code/đầu vào/plan giữ nguyên. Run đã hoàn
thành không ghi đè. Review/correction phải lưu riêng, giữ output judge gốc.

`metrics.json` có mean/mẫu số/usage/hash; `REPORT.md` có assertion, reasons,
citation judgments và câu hỏi suy ngược. `cases/` và `checkpoints/` giữ quyết
định có checksum; không log secret hoặc exception thô. Chi phí chấm tách
khỏi latency/token của chatbot; không stage outputs vào Git.

## Tham khảo

- [Ragas Factual Correctness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/factual_correctness/).
- [Ragas Faithfulness](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/faithfulness/).
- [Ragas Answer Relevancy](https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/answer_relevance/).
- [ALCE — EMNLP 2023](https://aclanthology.org/2023.emnlp-main.398/).

## Kết quả đã chạy tại workspace phát triển

Run `generation-claims-20261014-v1` chấm 50 đáp án đã lưu của
`rag-modules-v2-20261014-v1`, OpenAI `gpt-6-luna`, cùng cấu hình run gốc.
Báo cáo local: `outputs/evaluation/generation-claims-20261014-v1/SUMMARY.md`.
Bản judge thô, phục hồi lỗi validation và bản review có AI hỗ trợ được lưu
tách riêng; dùng đúng tên phiên bản và mẫu số khi đưa số liệu vào báo cáo.
Các kết quả chưa được chủ dự án duyệt toàn bộ, không phải nhãn chuyên gia
độc lập. Không chạy lại RAG hay mở held-out trong lượt chấm này.
