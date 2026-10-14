# Đề xuất nguồn về độ tuổi chịu xử phạt

Ngày 14/10/2026; cutoff 22/09/2026. Hồ sơ này được chuẩn bị trước ingestion.
**Owner đã duyệt bổ sung phần cần thiết trong lượt tiếp theo cùng ngày;
bốn phạm vi đã được nhập vào structured-law-v2.** Review kỹ thuật có AI hỗ trợ;
đây là duyệt phạm vi nguồn, không phải owner đã chấm toàn bộ đáp án.
Xem [phạm vi đã nhập và registry](LEGAL_SCOPE.md#nguồn-lõi-và-dependency-gate).
Đây là hồ sơ cụ thể để quyết định mở rộng phạm vi theo
[dependency gate](LEGAL_SCOPE.md#nguồn-lõi-và-dependency-gate).

## Nhu cầu và phạm vi đề xuất

Ứng dụng cần trả lời điều kiện tuổi chịu xử phạt hành chính trong tình huống
giao thông, phân biệt không xử phạt, cảnh cáo và phạt tiền đối với người chưa
thành niên. Nguồn lõi về quy tắc giao thông/mức phạt chưa đủ để quyết định điều
kiện này. Câu đã biết 043 bộc lộ khoảng thiếu; không dùng riêng citation của
benchmark làm lý do nhập toàn bộ luật.

Đề xuất **include bốn phạm vi** của Luật Xử lý vi phạm hành chính, đọc qua
90/VBHN-VPQH năm 2026; giữ đủ dẫn nhập và toàn bộ nội dung trong mỗi phạm vi:

| Phạm vi | Trang PDF | Nội dung cần cho sản phẩm |
| --- | ---: | --- |
| Điểm a khoản 1 Điều 5 | 6 | Ngưỡng tuổi và điều kiện cố ý; giữ nguyên cả đoạn tiếp theo trong điểm a |
| Khoản 5 Điều 11 | 10 | Loại trừ minh thị người chưa đủ tuổi bị xử phạt; dẫn chiếu tới điểm a khoản 1 Điều 5 |
| Điều 22 | 17 | Điều kiện cảnh cáo; phân biệt nhóm từ đủ 14 đến dưới 16 với người chưa đủ 14 tuổi |
| Khoản 3 Điều 134 | 88 | Giới hạn hình thức/mức xử phạt đối với người chưa thành niên; giữ đủ ba đoạn, không cắt bỏ điều kiện |

Hai phạm vi đầu trực tiếp giải quyết thiếu căn cứ của 043; hai phạm vi sau
giúp tránh khái quát sai khi người dùng hỏi nhóm tuổi liền kề. Không cần đưa
toàn bộ luật vào corpus cho nhu cầu này.

## Nguồn và hiệu lực

- [Trang văn bản của Chính phủ](https://chinhphu.vn/?docid=217377&pageid=27160):
  90/VBHN-VPQH, ngày 30/03/2026, Luật Xử lý vi phạm hành chính.
- [PDF chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/3/90-vbhn-vpqh.pdf),
  tải ngày 14/10/2026; 1.641.506 byte; SHA-256:
  `f60237d37fe965d4b15654747f53cfce60fb3c82cd76c597215882345bd6e20c`.
- [Công báo](https://congbao.chinhphu.vn/van-ban/van-ban-hop-nhat-so-90-vbhn-vpqh-469265/64066.htm)
  là nguồn đối chiếu thông tin công bố.

Bản 90 hợp nhất Luật 15/2012/QH13 cùng chín luật sửa đổi được liệt kê ở đầu
văn bản, gồm các sửa đổi hiệu lực 01/07/2026. Không dùng ngày hợp nhất làm
ngày hiệu lực của tất cả điều khoản. Ba phạm vi đầu không có chú thích sửa
đổi riêng trong bản 90; ngày hiệu lực ứng viên là 01/07/2013. Khoản 3 Điều 134
có chú thích 271, dẫn khoản 68 Điều 1 Luật 67/2020/QH14, hiệu lực 01/01/2022.
Cần giữ lineage và source spans riêng khi chuẩn bị ingestion.

Đã đối chiếu với [bản 171/2026/VBHN-LQ-VPQH ngày 30/09/2026](https://vanban.chinhphu.vn/?docid=219887&pageid=27160)
và [PDF chính thức](https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/10/171-vbhn-vpqh.signed.pdf).
Bản này nằm sau cutoff, bổ sung Luật 11/2026/QH16 có hiệu lực 01/03/2027;
không đưa nguyên bản vào serving tại cutoff. Nội dung thân của cả bốn phạm vi
nêu trên khớp bản 90 sau chuẩn hóa khoảng trắng; số chú thích có thể khác.
Việc đối chiếu này chỉ xác minh bốn phạm vi, không phải review toàn bộ luật.

## Giới hạn và nguy cơ hiểu quá phạm vi

- Không suy từ việc chưa đủ tuổi xử phạt rằng mọi trách nhiệm hoặc biện pháp
  khác đều không áp dụng. Không lấy cảnh cáo dành cho nhóm từ đủ 14 đến dưới
  16 tuổi áp cho trẻ chưa đủ 14 tuổi.
- Không mở phạm vi trách nhiệm hình sự/dân sự, trách nhiệm chủ xe khi giao xe,
  thủ tục tạm giữ/trả xe hoặc các biện pháp xử lý hành chính khác.
- Khoản 3 Điều 134 và dẫn nhập có tham chiếu Điều 3/khoản 1 Điều 126. Giữ
  nguyên tham chiếu nhưng đánh dấu ngoài phạm vi đã review; bốn đoạn này chưa
  đủ để trả lời riêng thủ tục, xử lý tang vật hoặc biện pháp khắc phục hậu quả.
- Không gắn cờ hoàn chỉnh toàn văn cho corpus chỉ nhập một phần. Mọi câu ngoài
  phạm vi được nguồn hỗ trợ vẫn cần giới hạn hoặc abstain.

## Hồ sơ đã chuẩn bị và bước triển khai sau duyệt

`outputs/legal-dependency-review-20261014-v1/candidate-review.json` (artifact local, không phát hành cùng Git)
chứa nguyên văn bốn đoạn, context cha, vị trí trang, hash text, ngày hiệu lực
ứng viên và giới hạn. PDF/text và biên nhận tải ở cùng thư mục; `downloads.json`
giữ cả lần tải đầu không thành công, `canonical-download.json` ghi lần tải
thành công từ URL PDF chính thức nêu trên. `pdftotext` có cảnh báo Flate ở
file nguồn; phần trích đang review đọc được và đã đối chiếu, chưa xác minh
toàn bộ text extraction. Không sử dụng text toàn văn chưa review để build.

Quyết định đề xuất: include bốn phạm vi trên; exclude phần còn lại ở đợt này.
Người review kỹ thuật: Codex (AI); người duyệt phạm vi: **owner, 14/10/2026**,
với yêu cầu “bổ sung data thêm Luật Xử lí vi phạm hành chính nữa đi nếu cần thiết”.
Artifact candidate cũ vẫn giữ `publication_eligible=false`, `ingested=false`
để bảo toàn lịch sử. Bản approved riêng nằm trong
`data/legal_sources/administrative-age-v1/`, được manifest corpus v2 khóa hash.
Đã render và đối chiếu trực quan cả bốn trang PDF ở lượt ingestion.

Sau khi phạm vi được duyệt: thêm registry/review và source spans có checksum;
xây snapshot/index phiên bản mới, giữ nguyên bản frozen và mười nguồn đang bị
chặn; kiểm truy xuất/đáp án theo biên tuổi và trường hợp thiếu tuổi. Chưa coi
043 đã được sửa chỉ vì hồ sơ ứng viên chứa căn cứ cần thiết.
