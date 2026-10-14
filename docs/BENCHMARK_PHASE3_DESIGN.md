# Thiết kế Pha 3 — regression/challenge và held-out

Ngày lập: 11/10/2026. Corpus duy nhất: `roadlawqa-current-law-2026-09-22`.
Đây là thiết kế và draft development, **không phải dataset mới đã duyệt**.
Không sửa hai dataset Pha 2, protocol đã freeze, serving contract hoặc index.

## Ba bộ có vai trò khác nhau

| Bộ | Dùng để làm gì? | Được dùng chỉnh hệ thống? |
| --- | --- | --- |
| Legacy: 50 gold reviewed v1 | Baseline nội bộ trên câu đã sử dụng | Có; không báo là unseen |
| Development regression/challenge | Kiểm tra lỗi đã biết và khoảng trống cụ thể | Có; luôn ghi nhận exposed |
| Held-out mới | Đo trên rule families không dùng chọn cấu hình | Không; giữ kín tới run cuối đã khóa |

Regression là mục tiêu chống lỗi tái xuất hiện; challenge là mục tiêu thử
điều kiện khó. Hai nhãn có thể cùng thuộc development, không cần hai split hay
mỗi split thêm 50 câu. Một câu hỏi đổi cách diễn đạt/số/chủ thể trong cùng
quy tắc đã lộ vẫn thuộc development, không thành held-out.

Các case development mới dùng contract riêng, không giả một CSV row hay đáp án
lịch sử cho câu mới. Parent 50 và case dẫn xuất đều giữ `legacy/historically_used`
và cùng family; case dẫn xuất có `suite=development` để chỉ vai trò thử lỗi,
không phải đổi exposure/split của câu lịch sử. Không tự
chuyển approval của parent sang case mới hoặc giả có review độc lập mới.

## Coverage trước khi thêm câu

Tool `evaluation.phase3_design` tái kiểm tra frozen reviewed gold (bao gồm draft,
snapshot, source/bundle hashes), rồi lập coverage từ case/evidence thực tế:
loại câu, nhãn, facet, tag, history, support locators, nguồn và amendment.
Các counts/tag chỉ mô tả dataset, **không phải kết quả hệ thống đã pass/fail**.

Ưu tiên dựa trên rủi ro và khoảng trống, không dựa số lượng câu cho đẹp:

- tiền + điểm / tiền + chế tài bổ sung: có đủ và cố tình thiếu một phần;
- căn cứ đúng vị trí nhưng không chứng minh claim; trang bị khác hành vi sử dụng;
- rewrite giữ chủ thể/biên số; accumulated evidence không mất lần tìm trước;
- multi-turn và history gây nhiễu; thiếu dữ kiện khác thiếu dependency;
- negative-support policy; publish đủ nguồn để đo unnecessary abstention;
- amendment và temporal review có scope, không dùng ngày freeze để suy hiệu lực;
- biên số liền kề; 10 publication-blocked chunks và ngày ngoài cutoff.

Batch đầu: 16 draft development, mỗi bài gắn parent, mục tiêu lỗi, evidence,
reference answer và điều reviewer cần chốt. Đây là budget thử protocol, không
chứng minh đủ coverage. Bộ biên số và temporal dưới đây còn phải author/review
gold riêng; không copy đáp án parent sang nhánh có kết quả khác.

## End-to-end khác controlled replay

End-to-end lấy query/history rồi để retrieval hoạt động bình thường. Nhãn
publish/conditional/abstain là expectation nội dung theo corpus đã khóa.

Fixed-evidence replay dùng pool chủ động được chỉ định; ví dụ chỉ đưa căn cứ
tiền nhưng query còn hỏi điểm. Corpus vẫn có căn cứ điểm, nhưng **pool hiện tại
chưa đủ**. Expectation của stage là insufficient, trong khi full-corpus gold
của cùng bài vẫn publish. Không đổi gold thành abstain vì cố tình cắt evidence.

Bài đủ pool là control cho bài thiếu pool. Bài citation chỉ đưa leaf không
hỗ trợ claim phải bị phát hiện; citation tồn tại không đồng nghĩa supported.
Accumulation lưu từng batch và ordered union; không xem batch cuối là toàn pool.
Rewrite probe chỉ đo bảo toàn ý định, chưa giả một output rewrite đã xảy ra.
Không gộp replay/probe vào mẫu số end-to-end hoặc tính 16 biến thể như 16
rule families độc lập. Pha 4 mới triển khai adapter/runner và scoring.

## Held-out: giữ kín thực sự, không chỉ đổi tên file

Batch khởi đầu dự kiến 12 candidate: 2 family độc lập cho mỗi 6 cell trong
`plan.json`. Đây là mức tối thiểu thử workflow, không phải statistical power
hay tỷ lệ đại diện người dùng. Chốt số/family trước khi chạy cấu hình; nếu
corpus không đủ nguồn phù hợp thì sửa thiết kế công khai, không lách leakage.

1. Chỉ công khai cell/coverage budget và exclusion inventory, không query/gold.
2. Chủ dự án chỉ định người giữ bộ (custodian), author và reviewer. Author
   không tự duyệt; người chọn/chỉnh cấu hình không đọc query/gold held-out.
   Hiện chưa chỉ định các vai trò này, chưa có bộ giữ kín.
3. Author độc lập dùng đúng snapshot, không dùng output cấu hình để chọn câu.
   Có thể cùng loại lỗi với development, nhưng phải khác rule/answer family.
4. Gom family trước chia split. Chặn toàn family đã lộ và, ở bản đầu, toàn
   article có evidence ở legacy/development (kể cả context/distractor). Đây là
   quy tắc bảo thủ chống đổi family ID để hợp thức hóa paraphrase.
5. Reviewer kiểm tra ngữ nghĩa trùng với legacy/development, test/prompt/demo/
   output trước đây; string similarity chỉ là trợ giúp, không chứng minh unseen.
   Inventory từ gold không bao phủ hết exposure của model/pretraining; "held-out"
   ở đây chỉ tương đối với quá trình tuning/chọn cấu hình của dự án.
6. Giữ query/gold ở storage riêng không nằm trong workspace/context của tuner.
   Hash SHA256 là cam kết toàn vẹn, **không phải mã hóa hoặc access control**.
   Public receipt chỉ có digest, family/coverage metadata cần thiết và attestation.
7. Independent review, freeze gold/evidence/protocol trước run. Khóa config,
   prompt/model revisions, snapshot, top-k/retry budgets và danh sách C0–C4
   trước mở bộ; cấu hình không được chọn bằng điểm held-out.
8. Chạy một run matrix đã đăng ký; báo mọi case, lỗi pipeline và exclusions,
   không loại câu khó sau xem output. Lỗi dữ liệu sửa thành version mới và rerun
   cùng matrix. Nếu dùng failure để tune, cả family chuyển development; cần
   held-out mới cho lần đánh giá unseen tiếp theo. Không tái gắn `unseen`.

Không sinh query held-out trong chính session đang thiết kế/chỉnh hệ thống này.
Chưa có custodian/access boundary thì giữ trạng thái `not_authored`, không tạo
file câu hỏi rồi gọi nó là sealed. Metadata gate chỉ kiểm tra mâu thuẫn có thể
phát hiện tự động, không xác nhận độc lập pháp lý/bảo mật bằng một boolean.

## Thời gian và giới hạn pháp lý

- Mặc định cutoff 22/09/2026; không lấy ngày audit làm luật "mới nhất".
- 10 chunk blocked chỉ có thể là context để thử từ chối, không positive support.
- So các mốc trước/đúng/sau 2028/2029 kiểm tra giới hạn snapshot, không dự đoán
  luật tương lai. Không khẳng định chế tài cũ tiếp tục hoặc hết áp dụng.
- Ngày lịch sử cần proof riêng bao phủ toàn support; proof câu 9 không mở rộng
  sang rule khác, ngày khác hay gold mới chưa review.
- Biên 10/20 và lân cận của bài tốc độ phải đọc leaf/context từng nhánh, phân
  biệt inclusive/exclusive; không cộng tiền/điểm ngoài nguồn.
- Thiếu dependency/negative completeness vẫn fail closed; không ingest thêm
  văn bản để làm đẹp phân bố publish và không đổi production safety contract.

## Review, freeze và gate kế tiếp

Reviewer đọc `DEVELOPMENT.md`: kiểm tra query/history có giữ ý định không,
đáp án và từng ý bắt buộc có đúng context không, pool cố tình thiếu có thực sự
thiếu không, stage expectation và failure category có phù hợp không. Không chỉ
duyệt câu văn đáp án. Review cũ chỉ là provenance, không là approval 16 bài mới.

Thiết kế có manifest create-only, verifier byte-exact và binding tới reviewed
receipt/snapshot. Không có scoring/freeze command cho draft này. Muốn gold mới
phải tạo dataset version riêng có review records, full evidence/context hashes,
temporal checks và receipt. Không cập nhật checksum để hợp thức hóa thay gold.

Pha 3 chỉ xong khi development chọn dùng và held-out thật đã review/freeze,
coverage/family/exposure audit đạt. Pha 4 cần runner/replay, rubric partial
credit, denominators, error accounting và locked run configuration. **C0–C4
vẫn bị chặn**; design hoặc owner đồng ý triển khai không tự mở các gate này.
