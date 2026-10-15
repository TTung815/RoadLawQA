# Phạm vi pháp lý RoadLawQA V2

## Mốc áp dụng

- Lãnh thổ: pháp luật cấp trung ương của Việt Nam.
- Lĩnh vực: giao thông đường bộ.
- Mốc mặc định: pháp luật có hiệu lực tại ngày `2026-09-22`.
- Câu hỏi nêu ngày khác chỉ được trả lời khi corpus có nguồn hiệu lực tương ứng.
  Nếu không có, hệ thống phải nêu giới hạn và từ chối kết luận chắc chắn.

Tài liệu này định nghĩa phạm vi của corpus và evaluation. Nó không tuyên bố rằng
RoadLawQA thay thế tư vấn pháp lý cho một vụ việc cụ thể.

## Ma trận phạm vi

| Nhóm câu hỏi | Trạng thái | Nguồn lõi | Giới hạn |
| --- | --- | --- | --- |
| Khái niệm và quy tắc về hoạt động đường bộ | Hỗ trợ | 49/VBHN-VPQH | Chỉ quy định cấp trung ương có trong corpus. |
| Quy tắc, nghĩa vụ của người tham gia giao thông đường bộ | Hỗ trợ | 55/VBHN-VPQH | Phải giữ điều kiện, ngoại lệ và mốc hiệu lực. |
| Phương tiện, người lái, GPLX, điểm và phục hồi điểm | Hỗ trợ | 55/VBHN-VPQH; 168/2024/NĐ-CP được sửa đổi bởi 238/2026/NĐ-CP | Không suy ra thủ tục chi tiết từ văn bản ngoài corpus. |
| Mức phạt hành chính về giao thông đường bộ | Hỗ trợ | Effective view của 168 + 238 | Phải xác định đúng chủ thể, hành vi, loại xe, hậu quả và thời điểm. |
| Độ tuổi chịu xử phạt hành chính | Hỗ trợ có giới hạn | Bốn phạm vi 90/VBHN-VPQH (2026) đã review | Điểm a khoản 1 Điều 5, khoản 5 Điều 11, Điều 22, khoản 3 Điều 134; không bao gồm toàn bộ thủ tục/biện pháp xử lý. |
| Tình huống thiếu dữ kiện quyết định | Có điều kiện | Các nguồn lõi | Nêu điều kiện còn thiếu; không chọn một nhánh như sự thật. |
| Kết luận không áp dụng/không có chế tài | Có điều kiện | Nguồn có provenance đầy đủ trong phạm vi | Policy negative-support hiện tại vẫn áp dụng; thiếu evidence không chứng minh không áp dụng. |
| Trách nhiệm hình sự, dân sự, bảo hiểm | Ngoài phạm vi | Không có | Từ chối và nêu phạm vi. |
| Đăng ký, đăng kiểm, kinh doanh vận tải chi tiết | Ngoài phạm vi mặc định | Không có | Chỉ mở rộng sau dependency audit riêng. |
| Quy định địa phương, biển báo hoặc tổ chức giao thông tạm thời | Ngoài phạm vi | Không có | Không dùng luật trung ương để phủ định quy định tại chỗ. |
| Đường sắt, đường thủy, hàng không | Ngoài phạm vi | Không có | Từ chối và nêu lĩnh vực được hỗ trợ. |
| Khiếu nại, cưỡng chế, thủ tục xử phạt chi tiết | Ngoài phạm vi mặc định | Không có | Chỉ trả lời phần được quy định trực tiếp trong nguồn lõi. |

## Loại câu hỏi được đánh giá

1. `factual`: định nghĩa, nghĩa vụ, thời hạn, điều kiện hoặc quy tắc trực tiếp.
2. `penalty`: mức tiền, trừ điểm, hình thức bổ sung hoặc biện pháp khắc phục.
3. `scenario`: áp dụng nhiều điều kiện vào dữ kiện cụ thể.

Nhãn `publish` của dataset frozen tuân theo rubric tại thời điểm review.
Runtime hiện tại cho phép trả lời phần đã kiểm chứng hoặc hỏi rõ với giới hạn
cụ thể. Câu nhiều nhánh cần đủ dữ kiện để kết luận chắc chắn; nếu thiếu thì
trả lời có điều kiện hoặc hỏi làm rõ. [Hợp đồng runtime](ARCHITECTURE.md).

## Chính sách thời gian

- Mặc định dùng `legal_as_of=2026-09-22` và phải hiển thị/ghi nhận mốc này trong
  evaluation run.
- Hành vi xảy ra trước `2026-08-15` không tự động áp dụng Nghị định 238; Điều 21
  của Nghị định 238 yêu cầu áp dụng nghị định có hiệu lực tại thời điểm hành vi
  xảy ra và kết thúc.
- Quy định có ngày hiệu lực riêng trong tương lai phải mang interval hiệu lực ở
  cấp chunk/facet; trạng thái chung của văn bản không đủ.
- Khoản 2 Điều 35 của 55/VBHN-VPQH hiện là một chunk chứa đồng thời phạm vi đã
  áp dụng và phạm vi có mốc 2028/2029; chunk này bị chặn publication cho tới khi
  được tách facet và review riêng.
- Ba placeholder ghi rõ `(được bãi bỏ)` tại khoản 4 Điều 10 và Điều 83 của 49,
  cùng khoản 7 Điều 62 của 55 được giữ để truy nguyên nhưng không
  active/publishable.

## Nguồn lõi và dependency gate

Nguồn lõi hiện hành gồm:

- 49/VBHN-VPQH: canonical reading text của Luật Đường bộ;
- 55/VBHN-VPQH: canonical reading text của Luật Trật tự, an toàn giao thông đường bộ;
- 168/2024/NĐ-CP: văn bản gốc về xử phạt;
- 238/2026/NĐ-CP: văn bản sửa đổi trực tiếp Nghị định 168.

Không ingest một văn bản khác chỉ vì benchmark cũ dẫn nó. Dependency mới phải có:

1. nhóm câu hỏi sản phẩm cần hỗ trợ;
2. facet không thể giải quyết bằng nguồn lõi;
3. phạm vi điều/khoản cần thiết;
4. rủi ro tạo false completeness khi ingest một phần;
5. quyết định include/exclude và người duyệt.

Luật Xử lý vi phạm hành chính được bổ sung có review ngày 14/10/2026. Chỉ nhập điểm a
khoản 1 Điều 5, khoản 5 Điều 11, Điều 22 và khoản 3 Điều 134 từ bản hợp nhất
90/VBHN-VPQH năm 2026. Registry/review bổ sung nằm tại
`data/legal_sources/administrative-age-v1/`, nguồn tại
`data/raw/legal/90-vbhn-vpqh-2026/`; không sửa registry/corpus/gold frozen.
Bốn phạm vi được đóng băng cùng nguồn lõi trong bundle `structured-law-v2`;
manifest khóa checksum PDF, text, registry và review. Chỉ bật công bố những
phạm vi đã review; không suy đã có toàn bộ Luật Xử lý vi phạm hành chính.
Điều 3 và khoản 1 Điều 126 vẫn là dẫn chiếu chưa nhập; không kết luận đủ căn
cứ về thủ tục/tang vật/khắc phục hậu quả từ phần trích này. Không suy không
áp dụng mọi trách nhiệm khác khi chưa đủ tuổi xử phạt hành chính.
[Registry bổ sung](../data/legal_sources/administrative-age-v1/registry.json) và
[review nguồn](../data/legal_sources/administrative-age-v1/review.json) ghi phạm vi cùng checksum.

## Quy tắc citation

- Điều khoản của Luật Đường bộ và Luật Trật tự, an toàn giao thông đường bộ được
  dẫn theo 49/VBHN-VPQH hoặc 55/VBHN-VPQH; metadata giữ lineage tới luật gốc và
  văn bản sửa đổi.
- Phần không bị sửa của Nghị định 168 dẫn Nghị định 168/2024/NĐ-CP.
- Phần bị Nghị định 238 sửa phải nêu Nghị định 168/2024/NĐ-CP được sửa đổi, bổ
  sung bởi Nghị định 238/2026/NĐ-CP và giữ cả hai source locator.
- Effective view là artifact kỹ thuật, không được trình bày như văn bản hợp nhất
  chính thức.

- Nguồn tuổi chịu xử phạt dẫn theo điều/khoản/điểm của Luật Xử lý vi phạm
  hành chính, bản hợp nhất 90/VBHN-VPQH (2026); metadata giữ lineage và ngày
  hiệu lực riêng, không dùng ngày hợp nhất làm ngày hiệu lực.

## Hành vi an toàn

- Không tìm thấy nguồn không có nghĩa là hành vi được phép hoặc không bị phạt.
- Không dùng model confidence để chứng minh corpus đầy đủ.
- Không suy ra không áp dụng từ việc vắng nguồn. Có thể trả lời theo lệnh cấm,
  loại trừ minh thị hoặc áp dụng điều kiện/thời hạn đã được nguồn xác định; không
  phân loại chỉ dựa vào chữ “không”. Phạm vi kết luận phải được nguồn hỗ trợ.
- Mâu thuẫn hiệu lực, amendment chưa ánh xạ, OCR chưa duyệt hoặc citation không
  truy ngược được đều phải chặn build hoặc chặn publication.
