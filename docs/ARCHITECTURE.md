# Kiến trúc RoadLawQA

## Ranh giới các thành phần

Streamlit chỉ gọi HTTP API, không import model/retriever. FastAPI khởi tạo
provider, model và kết nối database khi cần; `/api/v1/health` không tải tài
nguyên. `LLMProvider` và `Retriever` là các hợp đồng thay thế provider/backend.

| Thành phần | Mã nguồn |
| --- | --- |
| Hội thoại và phạm vi | [chat.py](../backend/services/chat.py), [conversation_router.py](../ai/agent/conversation_router.py) |
| Điều phối RAG | [lean_retrieval.py](../backend/services/lean_retrieval.py), [answer.py](../backend/services/answer.py) |
| Truy xuất | [structured.py](../ai/retrieval/structured.py), [current_law.py](../ai/retrieval/current_law.py) |
| Thiết bị và batching | [devices.py](../ai/retrieval/devices.py), [reranking.py](../ai/retrieval/reranking.py) |
| Sinh và kiểm chứng | [answer_generator.py](../ai/agent/answer_generator.py), [citation_verifier.py](../ai/agent/citation_verifier.py) |
| Nguồn cấu trúc và index | [structured_corpus.py](../ingestion/structured_corpus.py), [structured_index.py](../ingestion/structured_index.py) |

## Hội thoại và query expansion

Lời chào/cảm ơn/câu hỏi khả năng khớp mẫu đơn giản có thể trả ngay. Tin nhắn
khác qua một lượt LLM router, trả:

- `intent`: legal, mixed, help, social, out_of_scope hoặc clarify.
- `standalone_query`: câu hỏi độc lập, giải quyết tham chiếu từ lịch sử.
- `retrieval_query`: một cách diễn đạt bổ sung để tìm nguồn, hoặc null.

Help/social/ngoài phạm vi dùng mẫu server, không dẫn luật để giải thích khả
năng bot. Mixed chỉ đưa phần giao thông vào RAG và thông báo giới hạn.
Các câu ngắn như “Xe máy” có thể là follow-up khi lịch sử xác định được ý.

Expansion đổi cách diễn đạt đời thường sang thuật ngữ tìm kiếm, không được
bịa loại xe, tuổi, điều kiện hoặc mức phạt. Server bỏ bản rỗng, trùng, dài hơn
800 ký tự, đổi tập số hoặc làm mất cụm phủ định ngắn. Câu đã có view câu hỏi
chính từ dẫn nhập thời gian giữ view đó. Đây là guard bảo thủ, có thể bỏ cả
paraphrase hợp lệ và không chứng minh tương đương ngữ nghĩa.

Câu hỏi độc lập luôn dùng cho generation, verification và tra dẫn chiếu.
Expansion không phải nguồn luật. Không có bảng ánh xạ riêng cho từng lỗi
benchmark, cũng không gọi thêm một LLM để sửa expansion bị loại.

## Corpus và truy xuất

Corpus frozen có 2.531 leaf chunk làm căn cứ provenance/gold. Corpus phục vụ
`structured-law-v2` có 1.759 đơn vị: 1.755 từ nguồn lõi và bốn phạm vi luật bổ
sung. Dẫn nhập cha được giữ; `source_processed_ids` nối về nguồn tham chiếu.
Mười nguồn chưa đủ điều kiện công bố vẫn bị chặn. [Phạm vi nguồn](LEGAL_SCOPE.md).

Weaviate `LawStructured20260922V2` kết hợp BM25 trên `lexical_text` với query
vector, alpha mặc định 0.5. Filter yêu cầu nguồn được công bố, có hiệu lực và
đúng cutoff trước khi chọn ứng viên.

Một lượt truy xuất có tối đa hai view: câu hỏi độc lập và expansion hoặc
facet câu hỏi chính/tuổi. Các pool được xen kẽ, khử trùng trong ngân sách
20 ứng viên thường hoặc 32 khi hỏi đồng thời, tối đa 40. Locator văn bản/Điều
minh thị trong câu hỏi độc lập có thể thêm tối đa 20 ứng viên.

Rerank một pass, mặc định lấy top 5. Query rerank ưu tiên facet tuổi/câu hỏi
chính, sau đó expansion được chấp nhận, cuối cùng là câu hỏi độc lập. Không
nối lặp hai câu dài vào reranker. Batch 4 được sắp theo độ dài để giảm padding.

Reranker có thể chạy trên MPS của Apple Silicon hoặc CUDA; embedding mặc định
CPU theo cấu hình đã đo trên Mac. Hybrid search chạy trong Weaviate trên CPU.
LLM OpenAI/Gemini gọi qua API, không chạy trên CPU/GPU của Mac.

## Dẫn chiếu, sinh đáp án và kiểm chứng

Sau retrieval, tra dẫn chiếu minh thị có giới hạn bổ sung điều kiện áp dụng:
tối đa hai phạm vi Điều, tám chunks thêm và 12.000 ký tự. Context cha trùng
được gửi một lần. Cơ chế này không lấy mọi khoản gần nhau để coi là evidence.

Trong request tới LLM, nguồn dùng alias ngắn; server ánh xạ alias chính xác
về ID thật, không fuzzy-match ID model bịa. Generator sinh claims và citation;
verifier kiểm nguồn/hiệu lực, con số và ngữ nghĩa hỗ trợ, gồm cả limitations.

Khi nháp không đạt, cho phép sửa tối đa một lần trên cùng evidence rồi kiểm
lại. API không công bố nháp vẫn bị chặn. Trạng thái gồm `answered`,
`partial_answer`, `needs_clarification`, `insufficient_evidence`,
`verification_failed`, `conversational` và `out_of_scope`.

Thiếu nguồn không chứng minh không có chế tài. Có thể trả lời có điều kiện
hoặc một phần đã kiểm chứng; không biến nguồn chưa rõ phạm vi áp dụng thành
kết luận chắc chắn. Verifier vẫn là thành phần có thể sai, không phải chứng
minh pháp lý hình thức.

## Calls và diagnostics

Câu luật qua chatbot thường dùng ba logical calls: router, generation,
verification. Sửa nháp thêm hai calls. Lời chào khớp mẫu không gọi LLM;
help/ngoài phạm vi qua router thường dùng một call. Retry lỗi provider có
ngân sách riêng, nên logical calls không bằng mọi HTTP request thực tế.

`retrieval_query` ghi expansion đã chấp nhận; `retrieval_queries` ghi câu hỏi
độc lập và expansion. `retrieval_attempts=1`; `grade=null` và `rewritten_query=null`
vì luồng phục vụ không chạy grading/rewrite/regrade cũ. Trace native ghi view
thực tế kể cả facet. `routing_ms` gồm xử lý lịch sử và expansion.

API trả lỗi đã lọc. Diagnostics offline có thể giữ draft để debug, nhưng không
lưu API key hoặc request thô tới provider.

## API và evaluation

| Endpoint | Mục đích |
| --- | --- |
| `POST /api/v1/answer` | Toàn chatbot, nhận query/history/top-k |
| `POST /api/v1/retrieve/inspect` | Truy xuất câu độc lập, không LLM/router; history bị từ chối |
| `POST /api/v1/retrieve` | Retrieval với contextualization khi có lịch sử |
| `POST /api/v1/retrieve/agentic` | Tên endpoint giữ tương thích; hiện dùng pipeline lean |

Evaluator RAG dùng cùng service luật/retriever nhưng không chạy router chatbot.
Điểm/latency evaluator không đại diện toàn bộ trải nghiệm hội thoại.
[Phương pháp đánh giá](EVALUATION_QUICKSTART.md).
