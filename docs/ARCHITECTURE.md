# Architecture

## Layers

Phụ thuộc một chiều, tầng dưới không import tầng trên:

```text
frontend (Streamlit)  ──HTTP──►  backend (FastAPI: routes, dependencies, conversation store)
                                     │
                                     ▼
                        ai/pipeline (chat → retrieval → answer)
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
               ai/agent         ai/retrieval        ai/llm
       (router, generator,   (hybrid search,    (OpenAI/Gemini)
          verifier)         rerank, lookup)
                                     │
                                     ▼
                         ingestion (corpus, index)
```

`ai/` không import `backend/` hay `evaluation/`, nên evaluation chạy đúng
pipeline mà API dùng. `LLMProvider` và `Retriever` là interface để thay
provider hoặc backend truy xuất.

| Component | Source |
| --- | --- |
| Chat pipeline | [chat.py](../ai/pipeline/chat.py), [retrieval.py](../ai/pipeline/retrieval.py), [answer.py](../ai/pipeline/answer.py), [results.py](../ai/pipeline/results.py) |
| Router, generator, verifier | [conversation_router.py](../ai/agent/conversation_router.py), [answer_generator.py](../ai/agent/answer_generator.py), [citation_verifier.py](../ai/agent/citation_verifier.py) |
| Retrieval | [structured.py](../ai/retrieval/structured.py), [neighborhood.py](../ai/retrieval/neighborhood.py), [reranking.py](../ai/retrieval/reranking.py), [runtime.py](../ai/retrieval/runtime.py) |
| API | [main.py](../backend/main.py), [api/v1/](../backend/api/v1/), [dependencies/](../backend/dependencies/), [conversations.py](../backend/services/conversations.py) |
| UI | [app.py](../frontend/app.py), [client.py](../frontend/client.py), [state.py](../frontend/state.py), [views.py](../frontend/views.py) |
| Corpus and index | [structured_corpus.py](../ingestion/structured_corpus.py), [structured_index.py](../ingestion/structured_index.py), [bootstrap.py](../ingestion/bootstrap.py) |

## Request Flow

### 1. Routing

Lời chào hoặc cảm ơn khớp mẫu được trả lời ngay, không gọi LLM. Tin nhắn khác
qua một lượt LLM router (reasoning `low`), trả về:

- `intent`: `legal`, `mixed`, `help`, `social`, `out_of_scope` hoặc `clarify`.
- `standalone_query`: câu hỏi độc lập, đã giải quyết tham chiếu tới lịch sử
  (ví dụ "Xe máy" → câu hỏi đầy đủ về xe máy).
- `retrieval_query`: cách diễn đạt bằng thuật ngữ pháp lý để tìm nguồn, hoặc null.

Câu ngoài phạm vi hoặc hỏi cách dùng nhận phản hồi mẫu. Câu `mixed` chỉ đưa
phần giao thông vào RAG. Server bỏ `retrieval_query` nếu rỗng, dài hơn 800 ký
tự, đổi các con số hoặc làm mất phủ định. `standalone_query` luôn là câu dùng
để sinh và kiểm chứng đáp án.

### 2. Retrieval

Corpus `structured-law-v2` có 1.759 đơn vị Điều/Khoản/Điểm, mỗi đơn vị giữ
dẫn nhập của điều cha. Weaviate kết hợp BM25 trên văn bản tách từ (PyVi) với
vector search, α = 0.5, chỉ trên nguồn được công bố và có hiệu lực.

- Tối đa hai view truy vấn: câu hỏi độc lập và `retrieval_query` (hoặc view
  về độ tuổi chịu xử phạt). Các pool được xen kẽ và khử trùng.
- Ngân sách ứng viên: 20 (câu hỏi đơn) hoặc 32 (câu hỏi kép), tăng theo
  `4 × top_k`, tối đa 40. Điều/văn bản được nêu tên trong câu hỏi thêm tối đa
  20 ứng viên.
- Reranker `bge-reranker-v2-m3` chấm một lượt, lấy top 10; batch sắp theo độ
  dài để giảm padding.

### 3. Reference Lookup

Bổ sung các điều khoản được dẫn chiếu minh thị (ví dụ "trừ trường hợp quy định
tại khoản 3"), có giới hạn: tối đa 8 chunk và 12.000 ký tự. Thứ tự ưu tiên:
dẫn chiếu sang văn bản khác → điểm trừ điểm/xử phạt bổ sung nêu tên điểm đã
truy xuất → dẫn chiếu trong cùng văn bản → quy tắc xử phạt nhiều hành vi.

### 4. Generation

Nguồn được gửi tới LLM bằng alias ngắn; server ánh xạ alias về ID thật và
không fuzzy-match ID do model bịa. Generator trả structured output với bốn
loại câu trả lời:

| Loại | Nội dung |
| --- | --- |
| `complete` | Các nhận định kèm citation |
| `partial` | Nhận định và ít nhất một giới hạn |
| `clarification` | Giới hạn và câu hỏi làm rõ |
| `abstain` | Chỉ giới hạn, không có nhận định |

Ngoại lệ minh thị ảnh hưởng phạm vi áp dụng được giữ ngay trong nhận định.

### 5. Verification

Verifier kiểm từng nhận định: nguồn có hỗ trợ không, có hiệu lực không, con số
và điều kiện có đúng không, giới hạn có liên quan không. Mức đầy đủ
(`completeness_reason`) và trạng thái trả lời (`response_reason`) được đánh
giá riêng. Nháp không đạt được sửa tối đa một lần trên cùng evidence rồi kiểm
lại; nháp vẫn không đạt thì không được công bố.

Trạng thái trả về: `answered`, `partial_answer`, `needs_clarification`,
`insufficient_evidence`, `verification_failed`, `conversational`, `out_of_scope`.

Thiếu nguồn không chứng minh hành vi không bị phạt; hệ thống trả lời có điều
kiện hoặc nêu giới hạn thay vì kết luận phủ định.

## LLM Calls

Một câu hỏi luật dùng ba lời gọi LLM: router, generation, verification; sửa
nháp thêm hai lời gọi. Lời chào khớp mẫu không gọi LLM. Router dùng reasoning
`low`: trên 10 lượt thử, kết quả giống `medium` nhưng nhanh hơn khoảng 0,9s.

API chỉ trả nội dung đã kiểm chứng và lỗi đã lọc; không log API key, request
thô hay nội dung exception.

## API

| Endpoint | Mục đích |
| --- | --- |
| `POST /api/v1/answer` | Toàn bộ chatbot: query, history, top-k |
| `GET/POST /api/v1/conversations` | Liệt kê / tạo cuộc trò chuyện |
| `GET/PATCH/DELETE /api/v1/conversations/{id}` | Mở / đổi tên / xóa |
| `POST /api/v1/conversations/{id}/messages` | Gửi tin nhắn; API đọc lịch sử đã lưu và lưu cả hai lượt |
| `POST /api/v1/retrieve` | Truy xuất, viết lại câu hỏi theo lịch sử khi có |
| `POST /api/v1/retrieve/inspect` | Chỉ truy xuất câu độc lập, không gọi LLM |
| `POST /api/v1/retrieve/evidence` | Truy xuất, rerank và tra dẫn chiếu, không sinh đáp án |
| `GET /api/v1/health` | Tiến trình còn sống; không tải model hay database |
| `GET /api/v1/ready` | Model và index đã nạp chưa |
