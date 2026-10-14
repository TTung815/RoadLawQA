# Thiết lập và chạy demo

Chạy lệnh từ repository root. Cần Python 3.11+, Docker để chạy Weaviate,
model cache và API key của provider được chọn. Không cần API key để kiểm
health hoặc truy xuất độc lập sau khi đã có tài nguyên local.

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
| `outputs/current-law-shadow-2026-09-22/` và `bm25_index.pkl` ở root | Không | Tài nguyên snapshot/provenance cho evaluator và backend frozen |
| Kết quả evaluation/diagnostics | Không | Đáp án, trace, plan và receipt của từng lượt |

**Clone repo chưa đủ để chạy demo đầy đủ.** Cách đã kiểm là dùng workspace
có sẵn hoặc khôi phục bộ tài nguyên cùng phiên bản từ máy phát triển. Hiện
chưa có gói bootstrap độc lập đã kiểm trên database trống hoặc bản phát hành
artifact tải công khai.

Builder `ingestion.structured_index` giữ các kiểm tra provenance và tái dùng
vector từ index v1; nó không phải lệnh cài đặt một bước trên máy sạch. Không
chạy builder để sửa lỗi thiếu receipt của database đang có. Cần bộ receipt,
collection và corpus khớp nhau; dữ liệu không khớp sẽ bị từ chối.

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
| `OPENAI_API_KEY` hoặc `GEMINI_API_KEY`/`GEMINI_API_KEYS` | Xác thực provider tương ứng |
| `RETRIEVAL_BACKEND=structured` | Index cấu trúc hiện hành |
| `EMBEDDING_DEVICE=cpu` | Thiết bị cho embedding query |
| `RERANKER_DEVICE=auto` | Chọn CUDA, rồi MPS, rồi CPU khi khả dụng |
| `ROADLAWQA_API_URL=http://127.0.0.1:8000` | Địa chỉ API mà Streamlit gọi |

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
đã sẵn sàng. Mở **Kiểm tra truy xuất** để kiểm index/model mà không gọi LLM.

## Thử hội thoại

1. Gửi “Chào bạn”: nhận lời giới thiệu.
2. Hỏi “Hiện nay, vượt đèn đỏ phạt bao nhiêu tiền?”: xem đáp án và nguồn.
3. Gửi “Xe máy”: kiểm việc hiểu câu hỏi tiếp nối.
4. Hỏi “Tôi hỏi về Luật Thuế được không?”: xem phản hồi giới hạn phạm vi.

Có thể gọi API trực tiếp; lệnh này đi qua pipeline thật và có thể gọi provider:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/answer \
  -H 'Content-Type: application/json' \
  -d '{"current_query":"Đi xe máy có phải đội mũ bảo hiểm không?","chat_history":[],"top_k":5}'
```

## Kiểm tra tài nguyên

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/integration -m integration -q
```

Test offline không gọi provider/mạng nhưng một số kiểm tra snapshot cần
bundle đã đóng băng ngoài Git. Con số 534 test đạt được đo trên workspace
có đủ tài nguyên, chưa xác nhận full suite trên clone mới hoàn toàn.
Integration cần Weaviate và cache model; database không chạy có thể khiến
smoke test bị skip, không được tính skip thành passed.

Kiểm checksum corpus/dataset khi đã có bộ tài nguyên provenance:

```bash
.venv/bin/python -m evaluation.current_law_snapshot --verify
.venv/bin/python -m evaluation.reviewed_current_law_dataset verify
.venv/bin/python -m evaluation.reviewed_development_dataset verify
```

Nếu gặp lỗi thiếu bundle, collection, model hoặc checksum, đọc tên tài nguyên
được báo và khôi phục bản khớp. Không xóa database hoặc sửa manifest để bỏ qua
kiểm tra. [Cách đọc và chạy evaluation](EVALUATION_QUICKSTART.md).
