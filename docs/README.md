# Tài liệu RoadLawQA

Bắt đầu từ [README dự án](../README.md) để xem tính năng, demo và giới hạn.

| Nhu cầu | Tài liệu |
| --- | --- |
| Cài đặt, chạy API/UI, tài nguyên ngoài Git | [SETUP.md](SETUP.md) |
| Router, query expansion, retrieval, generation và verification | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Phạm vi nguồn luật, hiệu lực và trích dẫn | [LEGAL_SCOPE.md](LEGAL_SCOPE.md) |
| Dataset, kết quả hiện có và cách đánh giá | [EVALUATION_QUICKSTART.md](EVALUATION_QUICKSTART.md) |
| Cấu trúc dữ liệu đánh giá và dependency | [evaluation/README.md](../evaluation/README.md) |

## Protocol và hồ sơ nguồn

Các tài liệu dưới đây là đầu vào hoặc hồ sơ truy nguyên của dữ liệu đã đóng
băng. Tên phiên bản được giữ để khớp code và manifest; chúng không phải lộ
trình phát triển hay cam kết mọi bước lịch sử còn nằm trong runtime hiện tại.

- [Protocol dataset ban đầu](BENCHMARK_PROTOCOL.md).
- [Protocol dataset đã review](BENCHMARK_PROTOCOL_REVIEWED_V1.md).
- [Thiết kế coverage/development](BENCHMARK_PHASE3_DESIGN.md).
- [Protocol development draft](BENCHMARK_DEVELOPMENT_DRAFT_V1.md).
- [Protocol evaluation lõi](BENCHMARK_CORE_EVALUATION.md).
- [Hồ sơ review nguồn tuổi chịu xử phạt](LEGAL_DEPENDENCY_AGE_REVIEW_2026_10_14.md).

Protocol được khóa checksum, không chỉnh nội dung để phù hợp với một lượt
chạy mới. Nhật ký phiên làm việc và báo cáo debug theo ngày được giữ local;
người dùng repository không cần chúng để hiểu thiết kế công khai.
