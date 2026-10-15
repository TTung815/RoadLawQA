# Setup

Chạy mọi lệnh từ thư mục gốc của repository. Cần API key OpenAI hoặc Gemini để
chatbot trả lời; health check và kiểm tra truy xuất không cần key.

## Docker

Chỉ cần Docker (Docker Desktop trên Mac/Windows).

1. Tạo `.env` từ file mẫu và điền `OPENAI_API_KEY` (hoặc key Gemini, xem
   [Configuration](#configuration)):

   ```bash
   cp .env.example .env
   ```

2. Chuẩn bị dữ liệu một lần: tải model embedding và reranker (khoảng 2,7 GB)
   đúng revision đã khóa vào `~/.cache/huggingface/hub`, embedding 1.759 đơn
   vị luật và nạp vào Weaviate (khoảng 4 phút trên CPU sau khi tải xong):

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yml run --rm bootstrap
   ```

   Lệnh kết thúc bằng `{"collection": "LawStructured20260922V2", "chunks": 1759}`.
   Chạy lại an toàn: model đã có không tải lại, index đã có chỉ được kiểm tra.

3. Chạy Weaviate, API và UI:

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yml up -d --build
   ```

4. Mở `http://localhost:8501`. Model đã nạp xong khi lệnh sau trả `"warmup": "done"`
   (khoảng 20 giây):

   ```bash
   curl http://127.0.0.1:8000/api/v1/ready
   ```

Index dựng bằng bootstrap đã được kiểm trên Weaviate trống: cùng 1.759 object
và thuộc tính, vector lệch tối đa 3,6×10⁻⁷ so với index dùng để đánh giá.

**Lưu ý:**

- Luôn có `--env-file .env` khi chạy `up` hoặc `run`: nó cung cấp
  `WEAVIATE_CLUSTER_HOSTNAME`; Weaviate bị tạo lại với hostname khác sẽ không
  mở được index đã lưu.
- Dừng bằng `docker compose -f docker/docker-compose.yml stop`. Không dùng
  `down -v`: lệnh này xóa volume chứa database.
- Docker trên Mac không dùng được GPU, nên embedding và reranker chạy CPU,
  chậm hơn chạy local khoảng 10 giây mỗi câu.
- Xem log: `docker compose -f docker/docker-compose.yml logs -f api`.

| Thành phần | Cách đưa vào container |
| --- | --- |
| Code và `data/` | Copy vào image `api` ([Dockerfile](../Dockerfile)) |
| UI | Image `ui` riêng, chỉ có Streamlit ([frontend/requirements.txt](../frontend/requirements.txt)) |
| `.env` | Đọc lúc chạy, không copy vào image ([.dockerignore](../.dockerignore)) |
| Model | Gắn từ `~/.cache/huggingface/hub` (đổi bằng `HF_HUB_CACHE_DIR`) |
| Receipt index | Gắn từ `outputs/structured-law-v2/` |
| Hội thoại | Volume `docker_chat_data`, tách khỏi bản chạy local |

## Local Development

Cần Python 3.11+ và Docker cho Weaviate.

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Nếu đã có `.env` thì không chép đè. Lần đầu trên máy mới, chuẩn bị model và
index bằng bootstrap (bước 2 ở trên, hoặc `.venv/bin/python -m ingestion.bootstrap`
khi Weaviate đang chạy).

Khởi động Weaviate, rồi chạy API và UI trong hai terminal:

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d weaviate
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
.venv/bin/python -m streamlit run frontend/app.py
```

UI: `http://localhost:8501`, API docs: `http://127.0.0.1:8000/docs`. Khi API
khởi động, index và model được nạp chạy nền (khoảng 15 giây trên Mac M3).
Khởi động lại API sau khi đổi code hoặc `.env`.

Trong thanh bên, **Dành cho nhà phát triển → Kiểm tra truy xuất** hiển thị
nguồn và thời gian từng bước, không gọi LLM.

## Configuration

Các biến chính trong `.env` ([.env.example](../.env.example)). Biến không khai
báo sẽ dùng giá trị mặc định trong file mẫu.

| Biến | Vai trò |
| --- | --- |
| `LLM_PROVIDER`, `LLM_MODEL_NAME` | Provider (`openai` / `gemini`) và model |
| `OPENAI_API_KEY`, `GEMINI_API_KEY` / `GEMINI_API_KEYS` | API key; Gemini nhận nhiều key cách nhau dấu phẩy |
| `OPENAI_REASONING_EFFORT`, `ROUTER_REASONING_EFFORT` | Reasoning của generation/verification (`medium`) và router (`low`) |
| `EMBEDDING_DEVICE`, `RERANKER_DEVICE` | `cpu`, `mps`, `cuda` hoặc `auto` |
| `WARMUP_ON_STARTUP` | Nạp model khi API khởi động; `false` để nạp ở câu hỏi đầu |
| `CHAT_DB_PATH` | File SQLite lưu hội thoại |
| `ROADLAWQA_API_URL` | Địa chỉ API mà Streamlit gọi |

## Testing

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/integration -m integration -q
```

Test offline không gọi mạng hay LLM. Integration test cần Weaviate và model
cache; test bị skip không tính là đạt. Test gọi LLM thật chỉ chạy khi bật riêng
(có phí):

```bash
ROADLAWQA_LIVE_LLM_TESTS=1 .venv/bin/python -m pytest tests/integration/test_verifier_scope.py -m integration -q
```

Kiểm checksum của benchmark:

```bash
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```

## Troubleshooting

| Triệu chứng | Nguyên nhân thường gặp |
| --- | --- |
| `/api/v1/ready` báo `"warmup": "failed"` | Weaviate chưa chạy, chưa chạy bootstrap, hoặc thiếu model cache |
| UI báo chưa kết nối được API | API chưa chạy hoặc `ROADLAWQA_API_URL` sai |
| `Ports are not available` khi chạy Docker | Bản local đang dùng cổng 8000/8501; dừng nó trước |

Không xóa database hoặc sửa manifest để bỏ qua lỗi: hệ thống từ chối dữ liệu
không khớp receipt.
