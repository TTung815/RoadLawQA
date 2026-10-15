# Thiết lập và chạy demo

Chạy lệnh từ repository root. Cần Python 3.11+, Docker để chạy Weaviate,
model cache và API key của provider được chọn. Không cần API key để kiểm
health hoặc truy xuất độc lập sau khi đã có tài nguyên local.

## Máy mới: chạy bằng Docker

Chỉ cần Docker (Docker Desktop trên Mac/Windows) và API key OpenAI hoặc Gemini.

1. Clone repository rồi tạo `.env` từ file mẫu, điền `OPENAI_API_KEY` (hoặc
   key Gemini, xem [biến môi trường](#môi-trường-python-và-provider)):

   ```bash
   cp .env.example .env
   ```

2. Chuẩn bị dữ liệu một lần: tải model embedding/reranker (khoảng 2,7 GB) đúng
   revision đã khóa vào `~/.cache/huggingface/hub`, rồi embedding 1.759 đơn vị
   luật trong `data/processed/structured-law-v2/` và nạp vào Weaviate. Mất
   khoảng 4 phút trên CPU sau khi tải model xong.

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yml run --rm bootstrap
   ```

   Kết thúc bằng `{"collection": "LawStructured20260922V2", "chunks": 1759}` và
   receipt `outputs/structured-law-v2/index.json`. Chạy lại lệnh này an toàn:
   model đã có không tải lại, index đã có chỉ được kiểm tra, không dựng lại.

3. Chạy Weaviate, API và UI:

   ```bash
   docker compose --env-file .env -f docker/docker-compose.yml up -d --build
   ```

4. Mở `http://localhost:8501`. Khi `curl http://127.0.0.1:8000/api/v1/ready`
   trả `"warmup": "done"` (khoảng 20 giây) thì model đã nạp xong.

Index dựng theo cách này đã được kiểm trên Weaviate trống: cùng 1.759 object và
thuộc tính, vector lệch tối đa 3,6×10⁻⁷ so với index dùng cho kết quả đánh giá.
Chi tiết container ở [Chạy bằng Docker](#chạy-bằng-docker).

## Tài nguyên trong và ngoài Git

| Tài nguyên | Trong Git? | Mục đích |
| --- | --- | --- |
| Code, tests, `.env.example` | Có | Chạy ứng dụng và cấu hình mẫu |
| Nguồn/review/corpus tại `data/` | Có | Văn bản, provenance và đơn vị tìm kiếm |
| Dataset và protocol evaluation | Có | Câu hỏi/gold, kiểm phiên bản và checksum |
| `.env` | Không | Key và cấu hình local |
| Database Weaviate/volume | Không | Object và vector đã lập chỉ mục |
| `outputs/structured-law-v2/index.json` | Không | Receipt xác minh index hiện hành |
| Model cache embedding/reranker | Không | Trọng số đúng revision đã khóa |
| `outputs/current-law-shadow-2026-09-22/` và `bm25_index.pkl` ở root | Không | Tài nguyên snapshot/provenance mà bước kiểm corpus frozen cần |
| Kết quả evaluation/diagnostics | Không | Đáp án, trace, plan và receipt của từng lượt |

Database, receipt và model cache được tạo lại bằng
[`ingestion.bootstrap`](../ingestion/bootstrap.py) (bước 2 ở trên). Bootstrap
chỉ dựng index khi Weaviate chưa có collection; collection đã có phải khớp
receipt, nếu không sẽ bị từ chối. Không xóa database hoặc receipt để ép dựng
lại. Snapshot provenance (`outputs/current-law-shadow-2026-09-22/`,
`bm25_index.pkl`) chỉ cần cho bước kiểm corpus frozen, không cần để chạy demo.

## Môi trường Python và provider

Trên máy chưa có `.venv`:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Tạo `.env` từ [.env.example](../.env.example) nếu chưa có file. Không chép đè
cấu hình đã tồn tại. Điền key của provider bạn chọn; không đưa key vào Git.
File mẫu chọn OpenAI; adapter Gemini cũng được hỗ trợ. Model availability và
quyền truy cập phụ thuộc tài khoản provider.

Các biến chính:

| Biến | Vai trò |
| --- | --- |
| `LLM_PROVIDER`, `LLM_MODEL_NAME` | Provider và model cho router/generation/verification |
| `OPENAI_REASONING_EFFORT=medium`, `ROUTER_REASONING_EFFORT=low` | Mức reasoning của generation/verification và riêng của router |
| `OPENAI_API_KEY` hoặc `GEMINI_API_KEY`/`GEMINI_API_KEYS` | Xác thực provider tương ứng |
| `RETRIEVAL_BACKEND=structured` | Index cấu trúc hiện hành |
| `EMBEDDING_DEVICE=cpu` | Thiết bị cho embedding query |
| `RERANKER_DEVICE=auto` | Chọn CUDA, rồi MPS, rồi CPU khi khả dụng |
| `ROADLAWQA_API_URL=http://127.0.0.1:8000` | Địa chỉ API mà Streamlit gọi |
| `WARMUP_ON_STARTUP=true` | Nạp index, embedding và reranker chạy nền khi API khởi động; `false` để nạp khi có câu hỏi đầu tiên |
| `CHAT_DB_PATH` | File SQLite lưu hội thoại; mặc định `outputs/chat/conversations.sqlite3` (không đưa vào Git) |

`RERANKER_DEVICE=mps` yêu cầu GPU MPS thực sự khả dụng, lỗi rõ ràng nếu không.
Lần gọi đầu tải model/kết nối database nên có thể lâu hơn các lượt đã warm-up.
Loader dùng model cache local và revision trong snapshot/settings; không tự
đổi model hoặc âm thầm tải một revision khác.

## Khởi động database và ứng dụng

Với container hiện có trong workspace phát triển:

```bash
docker start docker-weaviate-1
```

Nếu dùng bản khôi phục có tên container khác, thay tên tương ứng. File Compose
ở [docker/docker-compose.yml](../docker/docker-compose.yml); cổng mặc định là
8080 (HTTP), 50051 (gRPC). Phải giữ hostname và volume của bản database đã lưu;
không tạo volume mới rồi coi nó là index đã chuẩn bị.

Terminal 1:

```bash
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
.venv/bin/python -m streamlit run frontend/app.py
```

UI: `http://localhost:8501`. Swagger: `http://127.0.0.1:8000/docs`.
Khởi động lại API sau khi thay code/settings; tải lại UI nếu thay giao diện.

Kiểm tiến trình API:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Health không tải model, provider hoặc database; `ok` không bảo đảm truy xuất
đã sẵn sàng. Trong thanh bên, mở **Dành cho nhà phát triển** rồi bật
**Kiểm tra truy xuất** để kiểm index/model mà không gọi LLM.

## Chạy bằng Docker

Thay cho hai terminal ở trên, Compose chạy cả ba service: `weaviate`
(database), `api` (FastAPI + retrieval) và `ui` (Streamlit); service
`bootstrap` chỉ chạy khi gọi `run` (máy mới, xem đầu trang). Image không chứa
model, key hay index; chúng được gắn vào lúc chạy.

```bash
docker compose --env-file .env -f docker/docker-compose.yml up -d --build
```

Luôn giữ `--env-file .env`: nó cung cấp `WEAVIATE_CLUSTER_HOSTNAME` của
database đã lưu; thiếu cờ này Compose sẽ tạo lại Weaviate với hostname khác và
không mở được index. Dừng bằng `docker compose -f docker/docker-compose.yml
stop` (không dùng `down -v`, lệnh đó xóa volume).

| Thành phần | Cách đưa vào container |
| --- | --- |
| Code và `data/` | Copy vào image `api` ([Dockerfile](../Dockerfile), target `api`) |
| UI | Image `ui` riêng, chỉ Streamlit + httpx ([frontend/requirements.txt](../frontend/requirements.txt)) |
| `.env` | `env_file` lúc chạy, không copy vào image ([.dockerignore](../.dockerignore)) |
| Model cache | Gắn chỉ đọc từ `~/.cache/huggingface/hub` (đổi bằng `HF_HUB_CACHE_DIR`) |
| Receipt index | Gắn chỉ đọc từ `outputs/structured-law-v2/` |
| Hội thoại đã lưu | Volume `docker_chat_data`, tách khỏi file SQLite khi chạy bằng `.venv` |

Container dùng CPU cho embedding và reranker vì Docker trên Mac không truy cập
GPU MPS, nên chậm hơn chạy trực tiếp; demo trên Mac vẫn nên dùng `.venv`.
API và UI chỉ mở ở `127.0.0.1` (cổng 8000 và 8501), nên dừng bản `.venv` trước
khi chạy Docker. Xem log bằng
`docker compose -f docker/docker-compose.yml logs -f api`.

## Thử hội thoại

1. Gửi “Chào bạn”: nhận lời giới thiệu.
2. Hỏi “Hiện nay, vượt đèn đỏ phạt bao nhiêu tiền?”: xem đáp án và nguồn.
3. Gửi “Xe máy”: kiểm việc hiểu câu hỏi tiếp nối.
4. Hỏi “Tôi hỏi về Luật Thuế được không?”: xem phản hồi giới hạn phạm vi.

Có thể gọi API trực tiếp; lệnh này đi qua pipeline thật và có thể gọi provider:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"current_query":"Đi xe máy có phải đội mũ bảo hiểm không?","chat_history":[],"top_k":10}'
```

## Kiểm tra tài nguyên

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/integration -m integration -q
```

Test offline không gọi provider/mạng nhưng một số kiểm tra snapshot cần
bundle đã đóng băng ngoài Git. Con số 566 test đạt được đo trên workspace
có đủ tài nguyên, chưa xác nhận full suite trên clone mới hoàn toàn.
Integration cần Weaviate và cache model; database không chạy có thể khiến
smoke test bị skip, không được tính skip thành passed.

Regression phạm vi verifier cần gọi LLM thật, dùng provider/model trong
`.env` và chỉ chạy khi bật riêng (năm trường hợp, có thể phát sinh phí):

```bash
ROADLAWQA_LIVE_LLM_TESTS=1 .venv/bin/python -m pytest tests/integration/test_verifier_scope.py -m integration -q
```

Kiểm checksum corpus/dataset khi đã có bộ tài nguyên provenance:

```bash
.venv/bin/python -m evaluation.current_law_snapshot --verify
.venv/bin/python -m evaluation.revised_current_law_dataset verify
```

Nếu gặp lỗi thiếu bundle, collection, model hoặc checksum, đọc tên tài nguyên
được báo và khôi phục bản khớp. Không xóa database hoặc sửa manifest để bỏ qua
kiểm tra. [Cách đọc và chạy evaluation](EVALUATION_QUICKSTART.md).
