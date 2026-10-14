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
Khi người dùng đổi đối tượng trong câu hỏi tiếp, router được hướng dẫn giữ
loại yêu cầu gốc của người dùng. Chi tiết trợ lý tự thêm ở lượt trước không
tự trở thành yêu cầu mới; expansion cũng phải giữ phạm vi đó.
Nếu lượt mới hỏi rõ mức phạt, ưu tiên yêu cầu mới và giữ chủ thể/hành vi từ
lịch sử. Expansion chuẩn hóa cả tên nhóm phương tiện và hành vi khi có cách
diễn đạt pháp lý tương đương, giữ các thuộc tính phân biệt nhóm xe.

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
tối thiểu 20 ứng viên thường hoặc 32 khi hỏi đồng thời; ngân sách tăng theo
`4 × top_k`, tối đa 40. Với `top_k=10`, ngân sách hybrid là 40 ứng viên.
Locator văn bản/Điều minh thị trong câu hỏi độc lập có thể thêm tối đa 20 ứng viên.

Rerank một pass, mặc định lấy top 10 chunk chính (hoặc ít hơn nếu không đủ
nguồn hợp lệ). Query rerank ưu tiên facet tuổi/câu hỏi chính, sau đó expansion được chấp nhận, cuối cùng là câu hỏi độc lập. Không
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
Generator dùng `GeneratedAnswer` với trường `answer` có bốn nhánh schema:
complete có claims nhưng không có giới hạn/câu hỏi làm rõ; partial có claims
và ít nhất một giới hạn; clarification có giới hạn và câu hỏi; abstain chỉ
có giới hạn, không có claims/câu hỏi. Nội dung và phần thiếu được sinh trước
khi chọn response_kind. Kết quả được chuyển về `DraftAnswer` phẳng để giữ
hợp đồng API, verifier và trace hiện có. Không tự đổi nháp partial thành complete.
Schema ngăn mâu thuẫn cấu trúc; giới hạn bịa hoặc nhận định sai vẫn phải bị
verifier chặn. Provider trả sai cấu trúc thì API báo lỗi generation đã lọc,
không công bố nháp hay tự thêm retry. Preflight kiểm schema generation mới.
Nhánh schema được đặt trong object gốc theo
[hợp đồng Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas).

Generator và verifier đánh giá mức đầy đủ theo ý được hỏi. Cho phép bổ sung
mức phạt hữu ích sau câu trả lời chính nếu có nguồn và ghi rõ điều kiện/phạm
vi; mọi claim bổ sung vẫn phải qua kiểm chứng. Phần bổ sung không tự tạo thêm
yêu cầu bắt buộc hoặc giả làm danh sách đầy đủ. Mỗi limitation phải liên quan đến ý chưa giải
quyết hoặc điều kiện cần để giải quyết ý đó. Giới hạn về chế tài không được
hỏi phải được sửa trong nháp, thay vì chỉ ẩn trên UI hoặc đổi nhãn thành công.
Nếu người dùng hỏi rõ về điểm hay toàn bộ chế tài, vẫn phải giữ và kiểm ý đó.
Khi chỉ hỏi quy tắc, phần tự bổ sung ưu tiên một ví dụ ngắn có nguồn; câu hỏi
mức phạt/nhiều nhánh vẫn cần đủ các nhánh được hỏi. Câu hỏi quy định chung đã
được giải đáp theo từng nhóm không phải hỏi lại để chọn nhóm cho người dùng.
Hành vi khác cùng chủ đề trong evidence không tự trở thành ý bắt buộc; vẫn
phải trả đủ khi người dùng hỏi nhiều hành vi. Generator giữ ngoại lệ minh
thị ảnh hưởng phạm vi áp dụng ngay trong claim tương ứng.

Verifier trả lý do ngắn `Đạt.` cho mục được hỗ trợ, giữ một câu giải thích
cụ thể cho lỗi hoặc ý còn thiếu để sửa nháp. Mỗi claim vẫn được đánh giá
riêng; định dạng gọn không bỏ kiểm nguồn, điều kiện, biên số hoặc giới hạn.

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
