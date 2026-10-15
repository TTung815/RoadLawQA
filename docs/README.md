# Tài liệu RoadLawQA

Bắt đầu từ [README dự án](../README.md) để xem tính năng, demo và giới hạn.

| Nhu cầu | Tài liệu |
| --- | --- |
| Cài đặt, chạy API/UI, tài nguyên ngoài Git | [SETUP.md](SETUP.md) |
| Router, query expansion, retrieval, generation và verification | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Phạm vi nguồn luật, hiệu lực và trích dẫn | [LEGAL_SCOPE.md](LEGAL_SCOPE.md) |
| Dataset, kết quả hiện có và cách đánh giá | [EVALUATION_QUICKSTART.md](EVALUATION_QUICKSTART.md) |
| Cấu trúc dữ liệu đánh giá và dependency | [evaluation/README.md](../evaluation/README.md) |

## Dữ liệu nguồn

Registry, bản review và checksum của nguồn pháp luật nằm trong
`data/legal_sources/`; văn bản gốc trong `data/raw/legal/`. Ground truth của
benchmark nằm trong `evaluation/datasets/current_law_20260922_reviewed_v2/`.
