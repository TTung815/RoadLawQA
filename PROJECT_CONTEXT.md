# RoadLawQA - Vietnamese Road Traffic Legal QA & Quiz RAG System
# Comprehensive Project Context & Technical Specification

> **Mục đích tài liệu:** Tài liệu này cung cấp toàn bộ bức tranh kiến trúc, luồng xử lý, tech stack, chi tiết từng module, đánh giá thực nghiệm và các hạn chế kỹ thuật hiện tại của dự án **RoadLawQA**. File này được thiết kế theo cấu trúc chuẩn ngữ cảnh (System Context Specification) để các hệ thống AI hoặc kỹ sư phần mềm có thể hiểu sâu sắc toàn bộ hệ thống ngay lập tức mà không cần đọc lại toàn bộ mã nguồn, từ đó dễ dàng hỗ trợ refactor, tối ưu hóa hoặc mở rộng tính năng.

---

## 1. Tổng quan Dự án (Executive Summary)

- **Tên dự án:** RoadLawQA (Hệ thống Hỏi Đáp & Trắc Nghiệm Luật Giao Thông Đường Bộ Việt Nam)
- **Bản chất:** Hệ thống Retrieval-Augmented Generation (RAG) chuyên biệt cho văn bản quy phạm pháp luật giao thông đường bộ Việt Nam.
- **Nguồn gốc:** Đồ án nhóm môn CS529 (Khoa Khoa học Máy tính - Đại học Công nghệ Thông tin UIT, ĐHQG-HCM), phát triển bởi sinh viên Nguyễn Thanh Tùng (phụ trách kiến trúc RAG core, pipeline dữ liệu, hybrid retrieval, reranker, answer generation) và các cộng sự.
- **Nhiệm vụ cốt lõi:**
  1. **Legal QA (Hỏi đáp pháp luật):** Tiếp nhận câu hỏi ngôn ngữ tự nhiên từ người dùng (tra cứu định nghĩa, mức xử phạt vi phạm hành chính, giải quyết tình huống giao thông), truy xuất căn cứ pháp lý chính xác và sinh câu trả lời có trích dẫn điều khoản cụ thể.
  2. **Quiz Generation (Sinh đề thi trắc nghiệm):** Tự động sinh bộ câu hỏi trắc nghiệm khách quan 4 lựa chọn (A, B, C, D) kèm đáp án, giải thích chi tiết và căn cứ pháp lý từ văn bản luật theo chủ đề người dùng yêu cầu hoặc ngẫu nhiên từ kho ngữ liệu.

### Phạm vi dữ liệu pháp lý hiện tại
Hệ thống hiện đang lập chỉ mục 3 văn bản pháp luật trọng yếu về an toàn giao thông và kết cấu hạ tầng đường bộ tại Việt Nam (ban hành năm 2024):
1. **Luật Trật tự, an toàn giao thông đường bộ 2024:** `Luật số 36/2024/QH15`
2. **Luật Đường bộ 2024:** `Luật số 35/2024/QH15`
3. **Nghị định quy định xử phạt vi phạm hành chính về trật tự, an toàn giao thông:** `Nghị định số 168/2024/NĐ-CP`

---

## 2. Tech Stack & Hạ tầng Kỹ thuật

| Thành phần | Công nghệ / Thư viện | Phiên bản | Vai trò & Lý do lựa chọn |
| :--- | :--- | :--- | :--- |
| **Ngôn ngữ chính** | Python | 3.11+ | Hệ sinh thái AI/NLP phong phú, xử lý chuỗi và dữ liệu nhanh |
| **Vector Database** | Weaviate | `1.24.10` (Client v4: `4.9.3`) | Lưu trữ vector embeddings, metadata và hỗ trợ HNSW index, gRPC port 50051 |
| **Vietnamese Word Tokenizer**| PyVi (`ViTokenizer`) | `0.1.1` | Tách từ tiếng Việt (compound word segmentation) phục vụ tính toán chỉ mục BM25 |
| **Sparse Retrieval (Keyword)**| `rank-bm25` (`BM25Okapi`)| `0.2.2` | Thuật toán BM25 tùy biến trên corpus đã tách từ qua PyVi, lưu file `bm25_index.pkl` |
| **Dense Embedding Model** | `Alibaba-NLP/gte-multilingual-base` | SentenceTransformers | Model 768 chiều, đa ngôn ngữ, biểu diễn ngữ nghĩa tiếng Việt tốt |
| **Cross-Encoder Reranker** | `BAAI/bge-reranker-v2-m3` | SentenceTransformers | Tái xếp hạng các ứng viên hybrid, tối ưu độ tương đồng query-document sâu |
| **Large Language Model (LLM)**| Google Gemini 2.5 Flash (`google-generativeai`)| `0.8.3` | Tốc độ sinh phản hồi nhanh, tuân thủ prompt nghiêm ngặt, chi phí thấp, hỗ trợ JSON Schema |
| **Frontend / Giao diện UI** | Streamlit | `1.41.1` | Giao diện web tương tác nhanh, hỗ trợ streaming, tabs và custom CSS |
| **Containerization** | Docker & Docker Compose | Compose v2 (v3.8 format) | Đóng gói và chạy Weaviate độc lập với persistence volume |
| **Framework học sâu / tính toán**| PyTorch (`torch`) | `2.5.1` | Chạy inference cục bộ cho embedding và reranker trên CPU/CUDA |

---

## 3. Kiến trúc Hệ thống (System Architecture)

```
                                  +-------------------------------------------------------+
                                  |                     NGUỒN DỮ LIỆU                     |
                                  |   data/raw: Luật 35, Luật 36, Nghị định 168 (.txt)     |
                                  +-------------------------------------------------------+
                                                              |
                                                              v
+-------------------------------------------------------------------------------------------------------------------------+
| OFFLINE DATA PIPELINE (backend/clean_and_split.py)                                                                      |
| - Parse cây phân cấp: Chương (Chapter) -> Mục (Section) -> Điều (Article) -> Khoản (Clause) -> Điểm (Point) -> Gạch     |
| - Chiến lược: Leaf-Only Chunking (chỉ lấy node lá sâu nhất) + Full Contextual Leaf Enrichment                           |
| - Bổ sung tags định danh: [CHAPTER], [ARTICLE], [CLAUSE], [POINT] vào từng leaf                                        |
| - Sliding window: Token > 1500 -> window 900, overlap 300                                                               |
| - Xuất file: data/processed/*.json (hàng ngàn leaf records cấu trúc cao)                                                |
+-------------------------------------------------------------------------------------------------------------------------+
                                                              |
                                                              v
+-------------------------------------------------------------------------------------------------------------------------+
| OFFLINE INDEXING PIPELINE (backend/build_index.py)                                                                      |
| 1. Kết nối Weaviate (Local instance qua Docker)                                                                        |
| 2. Khởi tạo Collection "LawChunks":                                                                                     |
|    - Vector config: Vectorizer.none() (Inference thủ công)                                                              |
|    - HNSW Index: Cosine distance, ef_construction=128, max_connections=64                                              |
|    - 6 Text properties cho BM25 Weaviate (article_no, article_title, clause_no, point, clause_head, text)                |
|    - Display & enrichment properties                                                                                    |
| 3. Mã hóa vector: Alibaba-NLP/gte-multilingual-base trên enriched_text -> Weaviate Batch Insert                         |
+-------------------------------------------------------------------------------------------------------------------------+
                                                              |
       +------------------------------------------------------+-------------------------------------+
       |                                                                                            |
       v                                                                                            v
+------------------------------------------------------+     +------------------------------------------------------+
| ONLINE RETRIEVAL PIPELINE (backend/retriever_custom.py) |     | RUNTIME INDEX CACHE                                  |
| 1. Query Analysis & Dynamic Alpha Tuning:            |     | - Load 10.000 chunks từ Weaviate vào RAM             |
|    - Nếu có số hiệu điều luật -> Alpha = 0.30        |     | - Build/Load bm25_index.pkl (BM25Okapi + PyVi)        |
|    - Nếu có đơn vị tiền / km/h -> Alpha = 0.40       |     +------------------------------------------------------+
|    - Mặc định / Semantic query -> Alpha = 0.75       |
| 2. Sparse Search: rank-bm25 với PyVi tokenizer       |
| 3. Dense Search: Weaviate near_vector (gte-base)     |
| 4. Score Normalization & Hybrid Combination:         |
|    Score = alpha * dense_score + (1 - alpha) * bm25  |
|    Lấy Candidate Pool = min(k * 4, 30)               |
| 5. Cross-Encoder Reranker (bge-reranker-v2-m3):      |
|    Predict(query, enriched_text) -> Top-K Chunks     |
+------------------------------------------------------+
       |
       +------------------------------------+
       |                                    |
       v (Raw Context & Sources)            v (Raw Chunks dict)
+-------------------------------+   +------------------------------------+
| QA GENERATOR                  |   | QUIZ GENERATOR                     |
| (backend/generator.py)        |   | (backend/generator.py, rag_quiz.py)|
| - Prompt template kiểm soát   |   | - QUIZ_PROMPT template (prompts.py)|
|   chặt chẽ nguồn luật         |   | - Format JSON Schema bắt buộc:     |
| - Gemini 2.5 Flash            |   |   question, options (A,B,C,D),     |
|   (temp=0.1, top_p=0.9)       |   |   correct_answer, explanation,     |
| - Bắt buộc trích dẫn:         |   |   citation                         |
|   "Căn cứ pháp lý: ..."       |   | - Phân bổ đều đáp án A/B/C/D       |
| - Từ chối nếu thiếu căn cứ    |   +------------------------------------+
+-------------------------------+                   |
       |                                            |
       +--------------------+-----------------------+
                            |
                            v
+-------------------------------------------------------------------------------------------------------------------------+
| PRESENTATION LAYER (frontend/app.py - Streamlit)                                                                        |
| - Tab 1: Chatbot QA (Giao diện bong bóng chat, bộ đếm latency (retrieval vs generation), expander căn cứ nguồn tham khảo)|
| - Tab 2: Luyện thi Trắc nghiệm (Chế độ theo chủ đề hoặc Random toàn luật, kiểm tra đáp án tương tác, xem giải thích)    |
+-------------------------------------------------------------------------------------------------------------------------+
```

---

## 4. Chi tiết Kỹ thuật Từng Module

### 4.1. Tiền xử lý & Chunking dữ liệu (`backend/clean_and_split.py`)
- **Vấn đề của tài liệu luật:** Nếu cắt chunk theo số lượng từ/token cố định (Fixed-size chunking), văn bản luật sẽ bị đứt gãy giữa chừng, mất ngữ cảnh của Điều và Chương cha, dẫn đến việc LLM trả lời sai hoặc không biết điều luật đó thuộc đạo luật nào.
- **Giải pháp - Hierarchical Leaf Chunking:**
  - Áp dụng biểu thức chính quy (regex) bóc tách toàn bộ văn bản theo hệ thống phân cấp hành chính chuẩn của văn bản quy phạm pháp luật Việt Nam:
    `Chương` $\rightarrow$ `Mục` $\rightarrow$ `Điều` $\rightarrow$ `Khoản` $\rightarrow$ `Điểm` $\rightarrow$ `Gạch đầu dòng (Bullet)`.
  - **Chỉ sinh chunk cho Node Lá (Leaf-only):** Thay vì index cả node cha lẫn node con gây trùng lặp, hệ thống chỉ tạo chunk cho cấp con sâu nhất (nếu Điều chỉ có Khoản thì leaf là Khoản; nếu Khoản có Điểm thì leaf là Điểm; nếu Điểm có Bullet thì leaf là Bullet).
  - **Full Contextual Leaf Enrichment:** Đây là kỹ thuật cốt lõi làm nên độ chính xác của hệ thống. Mỗi leaf chunk được tiêm ngữ cảnh đầy đủ vào trường `enriched_text`:
    ```
    [CHAPTER] Chương II. QUY TẮC GIAO THÔNG ĐƯỜNG BỘ
    [ARTICLE] Điều 10. Chấp hành báo hiệu đường bộ
    [CLAUSE] Khoản 3. Tín hiệu đèn giao thông
    [POINT] Điểm a) Tín hiệu đèn màu xanh là được đi...
    Nội dung chi tiết của leaf...
    ```
  - **Dữ liệu cấu trúc mỗi chunk:**
    - `id`: Mã định danh duy nhất (VD: `luatso-36-2024-QH15_D10_K3_a`).
    - `display_citation`: Chuỗi trích dẫn chuẩn người dùng nhìn thấy (VD: `điểm a khoản 3 Điều 10 Luật số 36/2024/QH15`).
    - `path`: Chuỗi breadcrumb đường dẫn phân cấp phục vụ tìm kiếm từ khóa.
    - `clause_head`: Phần dẫn nhập của khoản (tối đa 400 ký tự) nhằm giữ ngữ cảnh điều kiện áp dụng cho các điểm con.
    - `sliding_windows_by_tokens`: Nếu một node lá vượt quá 1500 tokens, tự động chia thành các sliding windows (cửa sổ 900 tokens, overlap 300 tokens) để không vượt ngữ cảnh embedding model.

### 4.2. Lập chỉ mục Vector & Metadata (`backend/build_index.py`)
- **Quản lý Schema trên Weaviate v4:**
  - Sử dụng API mới của Weaviate v4 (`weaviate.classes.config`).
  - Khởi tạo collection `LawChunks`. Tắt vectorizer tự động của Weaviate (`vectorizer_config=Configure.Vectorizer.none()`) để toàn quyền kiểm soát quy trình encode vector độc lập.
  - Cấu hình HNSW: `distance_metric=VectorDistances.COSINE`, `ef_construction=128`, `max_connections=64`.
- **Phân tách thuộc tính phục vụ tìm kiếm:**
  - **BM25 Searchable Fields:** `article_no`, `article_title`, `clause_no`, `point`, `clause_head`, `text`.
  - **Vectorized Content:** Chỉ encode `enriched_text` bằng model `Alibaba-NLP/gte-multilingual-base` (768 chiều). Chuẩn hóa vector (`normalize_embeddings=True`) trước khi nạp vào Weaviate.
  - Quá trình nạp thực hiện theo batch size = 64 để tối ưu throughput I/O.

### 4.3. Động cơ Truy xuất & Tái xếp hạng (`backend/retriever_custom.py`)
Hệ thống kết hợp 3 lớp truy xuất tối tân:

1. **Lớp 1: BM25 với Bộ tách từ tiếng Việt (PyVi Tokenizer):**
   - Bộ tìm kiếm BM25 mặc định của nhiều vector DB (kể cả Weaviate) chia từ theo khoảng trắng (whitespace/English standard), làm mất nghĩa các từ ghép tiếng Việt (ví dụ: "nồng độ cồn", "giấy phép lái xe", "vượt đèn đỏ").
   - `RoadLawQA` xây dựng riêng chỉ mục `BM25Okapi` bằng `pyvi.ViTokenizer`, lưu trữ offline trong `bm25_index.pkl`. Khi người dùng đặt câu hỏi, query được tokenize thành từ ghép trước khi chấm điểm BM25.
2. **Lớp 2: Dense Semantic Search (Weaviate):**
   - Encode query người dùng bằng `Alibaba-NLP/gte-multilingual-base` thành vector 768 chiều.
   - Tìm kiếm $k$ vector gần nhất trong Weaviate theo khoảng cách Cosine. Điểm cosine distance được chuyển đổi thành similarity: $Score_{dense} = 1.0 - Distance$.
3. **Lớp 3: Dynamic Alpha Tuning (Điều chỉnh trọng số lai động):**
   - Thay vì cố định trọng số $\alpha$ (Alpha giữa Dense và Sparse), hệ thống sử dụng Heuristics phân tích query:
     - Nếu query chứa từ khóa số hiệu pháp lý (`Điều 15`, `Khoản 2`, `Chương III`): Hệ thống giảm $\alpha = 0.30$ (ưu tiên BM25 keyword matching tuyệt đối).
     - Nếu query chứa các thông số kỹ thuật/mức phạt số học (`5 triệu`, `50 km/h`, `0.25 miligam`, `năm`): Hệ thống đặt $\alpha = 0.40$.
     - Nếu là câu hỏi tình huống, ngữ nghĩa chung: Hệ thống tăng $\alpha = 0.75$ (ưu tiên semantic vector search).
   - Công thức dung hợp:
     $$Score_{hybrid} = \alpha \cdot Score_{dense} + (1 - \alpha) \cdot Score_{bm25\_norm}$$
   - Số lượng ứng viên rút ra (Candidate Pool): $N = \min(k \times 4, 30)$.
4. **Lớp 4: Cross-Encoder Reranker (`BAAI/bge-reranker-v2-m3`):**
   - Đưa cặp `(query, enriched_text)` qua Cross-Encoder model. Reranker tính toán attention xuyên suốt giữa câu hỏi và toàn bộ ngữ cảnh điều luật, cho điểm tương quan chính xác hơn nhiều so với Bi-Encoder.
   - Sắp xếp và lấy ra top-$k$ kết quả chất lượng nhất (mặc định $k=5$).
5. **Cơ chế Truy xuất ngẫu nhiên (`retrieve_random`):**
   - Phục vụ việc sinh trắc nghiệm không trùng lặp: Sinh một vector ngẫu nhiên 768 chiều và truy vấn `near_vector` trong Weaviate để chọn ra các cụm điều luật phân tán.

### 4.4. Mô hình Sinh Ngôn ngữ & Kiểm soát Ảo giác (`backend/generator.py` & `backend/prompts.py`)
- **Mô hình:** Google Gemini 2.5 Flash.
- **Chiến lược Prompting (Anti-Hallucination Guardrails):**
  - Nhiệt độ thấp (`temperature=0.1`, `top_p=0.9`) để câu trả lời bám sát sự thật.
  - **Nguyên tắc vàng được cài đặt trong System Prompt:**
    1. Trả lời trực tiếp, rõ ràng, không vòng vo.
    2. Nếu liên quan đến xử phạt: Phải phân tách rõ đối tượng (ô tô, xe máy, xe đạp, người đi bộ) và khoảng tiền tệ cụ thể.
    3. Định dạng trích dẫn bắt buộc: Cuối phản hồi phải có `Căn cứ pháp lý:` liệt kê chính xác điểm/khoản/điều luật dựa trên thẻ `[Căn cứ: ...]` của context. Tuyệt đối không trích nguyên văn toàn bộ điều luật dài dòng.
    4. Từ chối trả lời nếu thiếu thông tin: *"Trong các trích dẫn luật được cung cấp, không có đủ thông tin để trả lời chính xác câu hỏi này."*
    5. Từ chối câu hỏi ngoài phạm vi an toàn giao thông đường bộ.
- **Sinh đề thi trắc nghiệm (`generate_quiz`):**
  - Tận dụng tính năng Structured Output của Gemini (`response_mime_type="application/json"`).
  - Ép khuôn cấu trúc trả về gồm: `question`, `options` (A, B, C, D), `correct_answer`, `explanation`, `citation`.
  - Phân bổ đều đáp án đúng giữa các lựa chọn A, B, C, D (chia đều $\approx 25\%$ cho mỗi lựa chọn).

### 4.5. Giao diện Người dùng (`frontend/app.py`)
- **Màn hình Welcome tương tác:** Thiết kế trang chủ giới thiệu với hình ảnh và nút bắt đầu hội thoại.
- **Tab Hỏi Đáp Luật:**
  - Lịch sử hội thoại dạng bong bóng chat hiện đại (User căn phải, Bot căn trái).
  - Khối hiển thị nguồn trích dẫn collapsible (`st.expander`), ngăn cách rõ ràng giữa văn bản giải thích và căn cứ luật.
  - Đo đạc thời gian thực (Real-time latency metrics): Hiển thị chi tiết thời gian tìm kiếm context ($T_{retrieval}$) và thời gian LLM sinh văn bản ($T_{generation}$).
  - Gợi ý sẵn 4 câu hỏi mẫu điển hình về luật giao thông.
- **Tab Tạo Đề Thi Trắc Nghiệm:**
  - 2 chế độ: "Theo chủ đề" (tìm kiếm theo keyword/ngữ nghĩa) hoặc "Ngẫu nhiên" (chọn ngẫu nhiên từ kho luật).
  - Tương tác trả lời trắc nghiệm trực tiếp: Chấm điểm Đúng/Sai ngay lập tức, mở rộng xem giải thích chi tiết và trích dẫn điều khoản.

---

## 5. Kết quả Đánh giá Thực nghiệm (Benchmark Evaluation)

Hệ thống đã được nhóm tác giả đánh giá trên bộ benchmark chuẩn gồm **50 câu hỏi luật giao thông** được gắn nhãn thủ công (Ground Truth) kèm điều khoản căn cứ chính xác, chia làm 3 nhóm:
- 15 câu tra cứu thực tế (Factual lookup)
- 15 câu tra cứu mức phạt vi phạm (Penalty lookup)
- 20 câu giải quyết tình huống giao thông (Scenario-based reasoning)

### 5.1. Đánh giá Động cơ Truy xuất (Retrieval Performance at $k=5$)

| Phương pháp truy xuất | Recall@5 | MRR@5 | nDCG@5 | HitRate@5 |
| :--- | :---: | :---: | :---: | :---: |
| **BM25 thuần** | 0.707 | 0.538 | 0.598 | 0.780 |
| **Dense (Vector) thuần** | 0.762 | 0.760 | 0.791 | 0.880 |
| **Hybrid (Dense + BM25 PyVi)** | 0.817 | 0.752 | 0.789 | 0.900 |
| **Hybrid + Reranker (bge-reranker-v2-m3)** | **0.817** | **0.796** | **0.827** | **0.920** |

> **Nhận xét:** Sự kết hợp giữa Hybrid Search và Cross-Encoder Reranker đẩy HitRate@5 lên **92.0%** và nDCG@5 lên **0.827**, vượt trội hoàn toàn so với việc chỉ dùng BM25 hoặc chỉ dùng Dense Vector đơn lẻ.

### 5.2. Đánh giá Độ chính xác Sinh câu trả lời (End-to-end Generation)

| Loại câu hỏi | Số lượng câu | Độ chính xác Pháp lý (Legal Accuracy) | Độ chính xác Trích dẫn (Citation Accuracy) | Độ tương quan (Relevance) |
| :--- | :---: | :---: | :---: | :---: |
| **Tra cứu thực tế** | 15 | **0.97** | 0.87 | 0.93 |
| **Tra cứu mức xử phạt** | 15 | **0.87** | 0.80 | 0.87 |
| **Suy luận tình huống** | 20 | **0.70** | 0.68 | 0.80 |
| **Toàn bộ (Overall)** | **50** | **0.83 (83%)** | **0.77 (77%)** | **0.86 (86%)** |

---

## 6. Các Điểm nghẽn, Vấn đề Hiện tại & Hạn chế Kỹ thuật

Bất kỳ AI hoặc kỹ sư nào muốn cải tiến dự án cần đặc biệt lưu ý những hạn chế đang tồn tại trong mã nguồn hiện tại:

### 6.1. Hạn chế về Quản lý Bộ nhớ & Kiến trúc Dữ liệu
1. **Load toàn bộ 10.000 Chunks vào RAM khi khởi động (`retriever_custom.py`):**
   - Hàm `load_chunks_from_weaviate()` truy vấn lấy toàn bộ dữ liệu từ Weaviate lên bộ nhớ RAM của Python script (`chunks_cache`) để phục vụ việc map index của BM25.
   - *Hậu quả:* Nếu dữ liệu luật tăng lên 100.000 chunks hoặc nhiều người truy cập, RAM sẽ bị quá tải (OOM). Chưa có cơ chế in-database BM25 hoặc inverted index tích hợp trực tiếp trên disk/vector database.
2. **File `bm25_index.pkl` tĩnh và cồng kềnh:**
   - File pickle lưu trực tiếp ở thư mục gốc (~1.4MB cho 3 luật). Nếu có cập nhật luật mới, file này không tự động đồng bộ mà phải chạy lại hàm build thủ công.

### 6.2. Hạn chế về Hiệu năng Tính toán (Latency & Resource Utilization)
1. **Inference Embedding & Reranker chạy trực tiếp trên CPU cùng tiến trình:**
   - Cả 2 model `gte-multilingual-base` và `bge-reranker-v2-m3` được load trực tiếp khi import `retriever_custom.py`.
   - Cấu hình đang gán cứng:
     ```python
     os.environ["OMP_NUM_THREADS"] = "1"
     torch.set_num_threads(1)
     torch.backends.mps.is_available = lambda: False
     ```
     Điều này vô hiệu hóa Apple Silicon GPU (MPS) và ép torch chạy đơn luồng (Single Thread) trên CPU, dẫn đến độ trễ reranking bị kéo dài khi số lượng candidate lớn.
2. **Khởi tạo và tải model tại thời điểm Import:**
   - Bất cứ script nào import `retriever_custom` (kể cả Streamlit khi rerun) đều bị khựng lại vài giây để load model nếu không được cache cẩn thận trong `st.cache_resource`.

### 6.3. Hạn chế về Khả năng Xử lý Hội thoại (Multi-turn Conversation & Contextual Query)
1. **RAG một lượt (Single-turn RAG):**
   - Giao diện Streamlit có hiển thị lịch sử chat, nhưng khi gọi `retrieve(last_user_question)`, hệ thống **chỉ gửi đúng câu hỏi cuối cùng của user**.
   - *Hệ quả:* Không hỗ trợ câu hỏi nối tiếp (follow-up questions).
     *Ví dụ:*
     - Lượt 1: *"Xe máy vượt đèn đỏ phạt bao nhiêu?"* $\rightarrow$ Trả lời: 800.000đ - 1.000.000đ.
     - Lượt 2: *"Còn ô tô thì sao?"* $\rightarrow$ Retriever sẽ tìm kiếm từ khóa *"Còn ô tô thì sao?"* và thất bại hoàn toàn vì thiếu ngữ cảnh "vượt đèn đỏ".
2. **Chưa có cơ chế Query Rewriting / Query Expansion:**
   - Chưa tích hợp LLM để diễn giải lại câu hỏi của người dùng (Hypothetical Document Embeddings - HyDE hoặc Multi-query expansion) trước khi đưa vào bộ tìm kiếm.

### 6.4. Hạn chế về Nghiệp vụ & Dữ liệu Pháp luật
1. **Phạm vi luật tĩnh và giới hạn:**
   - Chỉ có 3 văn bản: Luật 35, Luật 36 và Nghị định 168.
   - Chưa tích hợp các thông tư hướng dẫn thi hành, quy chuẩn kỹ thuật quốc gia về báo hiệu đường bộ (như QCVN 41:2019/BGTVT).
   - Chưa xử lý được mối quan hệ hiệu lực văn bản: Văn bản sửa đổi bổ sung, điều khoản bị bãi bỏ hoặc thay thế theo thời gian.
2. **Cơ chế `retrieve_random` còn ngây thơ:**
   - Dùng vector ngẫu nhiên Gaussian/Uniform để lấy chunk ngẫu nhiên cho đề thi trắc nghiệm. Phương pháp này khiến các vector phân bố không đều trong không gian cosine, dễ bị lệch cụm (cluster bias) vào một vài chương luật nhất định thay vì lấy mẫu phân tầng (stratified sampling) đều khắp các văn bản.
3. **Regex dọn dẹp căn cứ pháp lý đang bị comment:**
   - Trong `generator.py` (dòng 150-184), đoạn code Regex hậu xử lý chuỗi "Căn cứ pháp lý" đang bị comment lại, phụ thuộc 100% vào việc Gemini có format đúng markdown hay không.

### 6.5. Kiến trúc Đóng gói & Phân tầng (Architecture Decoupling)
1. **Thiếu Backend API độc lập:**
   - Frontend Streamlit đang import và gọi trực tiếp các module Python nội bộ (`backend.retriever_custom`, `backend.generator`).
   - Chưa có tầng REST API hoặc gRPC service (FastAPI) để tách rời client-server. Nếu muốn build app Mobile hoặc tích hợp Zalo Mini App / Webhook Messenger thì bắt buộc phải viết lại API.

---

## 7. Đề xuất Hướng Cải tiến Tiềm năng (Roadmap for AI & Developers)

Dành cho AI hoặc Developer muốn đề xuất nâng cấp hệ thống:

| Hướng cải tiến | Giải pháp kỹ thuật cụ thể | Mức độ ưu tiên |
| :--- | :--- | :---: |
| **1. Multi-turn Conversational RAG** | Thêm bước **Query Contextualization / History-aware Retriever**. Dùng LLM nhỏ hoặc Gemini tóm tắt lại lịch sử trò chuyện kết hợp câu hỏi mới thành một Standalone Search Query trước khi retrieve. | 🔴 Cao |
| **2. Tách Backend API (FastAPI)** | Đóng gói toàn bộ logic tìm kiếm và sinh đáp án thành RESTful endpoints (`/api/v1/chat`, `/api/v1/quiz`, `/api/v1/health`) với Pydantic validation và background async tasks. | 🔴 Cao |
| **3. Tối ưu Bộ nhớ & Tốc độ Retriever** | Thay thế việc load toàn bộ 10.000 chunks vào RAM bằng cách sử dụng trực tiếp tính năng Hybrid Search sẵn có của Weaviate v4 (kết hợp native BM25 + Vector) hoặc dùng Elasticsearch/Qdrant/Milvus; tận dụng GPU/MPS cho inference PyTorch. | 🟡 Trung bình |
| **4. Advanced Retrieval (HyDE / Multi-Query)** | Ứng dụng Hypothetical Document Embeddings (HyDE) để sinh giả lập một điều luật rồi mới encode tìm kiếm, hoặc phân rã câu hỏi tình huống phức tạp thành các sub-queries (Sub-question decomposition). | 🟡 Trung bình |
| **5. Agentic RAG / Tools Calling** | Xây dựng Agent giao thông có khả năng gọi tool: Tool tra cứu bảng phạt cụ thể (Penalty Calculator Tool), Tool phân tích biển báo giao thông qua hình ảnh (Multimodal Vision Tool), Tool kiểm tra nồng độ cồn. | 🟡 Trung bình |
| **6. Mở rộng Dữ liệu & Đồ thị Tri thức (Legal Knowledge Graph)** | Chuyển đổi dữ liệu luật từ dạng Chunk sang dạng Graph (GraphRAG): Biểu diễn quan hệ: *Hành vi $\rightarrow$ Quy tắc vi phạm $\rightarrow$ Mức phạt $\rightarrow$ Thẩm quyền xử phạt*. Bổ sung QCVN 41:2019/BGTVT. | 🟢 Nâng cao |
| **7. Đánh giá Tự động (LLM-as-a-Judge)** | Xây dựng pipeline đánh giá tự động bằng Ragas hoặc TruLens dựa trên các chỉ số: Faithfulness, Answer Relevance, Context Precision, Context Recall. | 🟢 Nâng cao |

---

## 8. Hướng dẫn Khởi chạy & Môi trường Phát triển (Quickstart)

```bash
# 1. Kích hoạt môi trường ảo
source .venv/bin/activate  # Trên Linux/macOS
# .venv\Scripts\activate   # Trên Windows

# 2. Cài đặt phụ thuộc
pip install -r requirements.txt

# 3. Cấu hình biến môi trường
cp .env.example .env
# Chỉnh sửa .env: GEMINI_API_KEY=AIzaSy...

# 4. Khởi chạy Weaviate Vector Database
docker compose -f docker/docker-compose.yml up -d

# 5. Tiền xử lý dữ liệu & Xây dựng Index
python backend/clean_and_split.py
python backend/build_index.py

# 6. Chạy ứng dụng giao diện
streamlit run frontend/app.py

# 7. Chạy kiểm thử dòng lệnh (CLI)
python backend/rag_qa.py
python backend/rag_quiz.py
```

---
*Tài liệu được khởi tạo tự động dựa trên phân tích toàn diện mã nguồn RoadLawQA. Dùng file này làm System Context chính xác nhất khi đưa vào các mô hình AI để thảo luận và nâng cấp hệ thống.*

