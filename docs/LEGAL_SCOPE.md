# Legal Scope

Pháp luật cấp trung ương của Việt Nam về giao thông đường bộ, có hiệu lực tại
**22/09/2026**. RoadLawQA không thay thế tư vấn pháp lý cho vụ việc cụ thể.

## Sources

| Văn bản | Nội dung | Phạm vi nhập |
| --- | --- | --- |
| 49/VBHN-VPQH | Luật Đường bộ (hợp nhất) | Toàn văn |
| 55/VBHN-VPQH | Luật Trật tự, an toàn giao thông đường bộ (hợp nhất) | Toàn văn |
| 168/2024/NĐ-CP + 238/2026/NĐ-CP | Xử phạt vi phạm hành chính, trừ/phục hồi điểm GPLX | Bản ghép kỹ thuật: 168 sau khi áp dụng sửa đổi của 238 |
| 90/VBHN-VPQH (2026) | Luật Xử lý vi phạm hành chính (hợp nhất) | Chỉ điểm a khoản 1 Điều 5, khoản 5 Điều 11, Điều 22, khoản 3 Điều 134 (độ tuổi chịu xử phạt) |

Registry, review và checksum từng nguồn nằm trong `data/legal_sources/`; văn
bản gốc trong `data/raw/legal/`. Có 10 đơn vị bị chặn công bố: 3 điều khoản đã
bãi bỏ (giữ để truy nguyên), khoản 2 Điều 35 của 55/VBHN-VPQH (lẫn quy định có
hiệu lực 2028/2029) và 6 điểm của Nghị định 168 không có hiệu lực tại mốc.

Một văn bản mới chỉ được bổ sung khi có nhóm câu hỏi cần nó, xác định rõ
điều khoản cần nhập và được review riêng.

## Coverage

| Nhóm câu hỏi | Trạng thái |
| --- | --- |
| Khái niệm, quy tắc tham gia giao thông, nghĩa vụ người tham gia | Hỗ trợ |
| Phương tiện, người lái, GPLX, trừ và phục hồi điểm | Hỗ trợ |
| Mức phạt hành chính về giao thông đường bộ | Hỗ trợ |
| Độ tuổi chịu xử phạt hành chính | Hỗ trợ có giới hạn (bốn phạm vi ở trên) |
| Tình huống thiếu dữ kiện quyết định | Trả lời có điều kiện hoặc hỏi rõ |
| Trách nhiệm hình sự, dân sự, bảo hiểm | Ngoài phạm vi |
| Đăng ký, đăng kiểm, kinh doanh vận tải chi tiết | Ngoài phạm vi |
| Quy định địa phương, biển báo tạm thời | Ngoài phạm vi |
| Đường sắt, đường thủy, hàng không | Ngoài phạm vi |
| Khiếu nại, cưỡng chế, thủ tục xử phạt chi tiết | Ngoài phạm vi |

## Effective Dates

- Mặc định áp dụng pháp luật có hiệu lực tại 22/09/2026. Câu hỏi nêu ngày khác
  chỉ được trả lời khi corpus có nguồn hiệu lực tương ứng.
- Hành vi xảy ra trước 15/08/2026 không tự động áp dụng Nghị định 238 (Điều 21
  Nghị định 238).
- Quy định có ngày hiệu lực riêng mang khoảng hiệu lực ở cấp chunk, không dựa
  vào trạng thái chung của văn bản.

## Citation Rules

- Luật Đường bộ và Luật Trật tự, an toàn giao thông đường bộ dẫn theo
  49/VBHN-VPQH và 55/VBHN-VPQH.
- Phần không bị sửa của Nghị định 168 dẫn Nghị định 168/2024/NĐ-CP; phần bị
  sửa dẫn "Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định
  238/2026/NĐ-CP".
- Bản ghép 168 + 238 là artifact kỹ thuật, không trình bày như văn bản hợp nhất
  chính thức.
- Quy định về độ tuổi dẫn theo 90/VBHN-VPQH (2026).

## Safety

- Không tìm thấy nguồn không có nghĩa là hành vi được phép hoặc không bị phạt.
- Chỉ kết luận "không áp dụng" khi nguồn quy định rõ (lệnh cấm, loại trừ, điều
  kiện, thời hạn), không chỉ dựa vào việc vắng nguồn.
- Mâu thuẫn hiệu lực, sửa đổi chưa ánh xạ hoặc citation không truy ngược được
  đều chặn việc dựng corpus hoặc công bố câu trả lời.
