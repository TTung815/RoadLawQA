# Bổ sung development draft v1 — biên số, thời gian và review gọn

Ngày lập 11/10/2026. Snapshot/cutoff vẫn `roadlawqa-current-law-2026-09-22`.
Không sửa packet design v1, gold/draft Pha 2, luật nguồn hoặc index đã khóa.
Tài liệu này mở rộng [thiết kế Pha 3](BENCHMARK_PHASE3_DESIGN.md), không tuyên bố
development hoặc held-out đã approved/freeze.

## Đơn vị và phân công

Packet mới tại `evaluation/datasets/current_law_20260922_development_draft_v1/`:

- giữ 16 bài design gốc bằng parent hash, không chuyển approval từ 50 gold;
- author 4 câu tiền phạt ở biên 9/10/20/21 km/h, đọc leaf và clause head từng nhánh;
- tạo 34 publication-guard probes: 10 locator bị block tại cutoff, và 24 probe
  trước/đúng/sau 8 mốc tương lai ghi trong metadata của 7 locator mixed/future;
- mọi gold mới vẫn `needs_review`, không có scoring/freeze command;
- Codex tự audit kỹ thuật/nguồn, không giả người review độc lập hoặc model run.

54 đơn vị là 20 bài design/numeric và 34 kiểm tra policy bằng evidence chỉ định.
Không phải 54 câu hỏi người dùng độc lập hoặc 54 rule families. Guard/replay/
rewrite không cộng vào mẫu số end-to-end. 4 numeric cùng family lịch sử
`car_speed_10_20`, vẫn `legacy/historically_used` ngay cả hai nhánh mới 9/21.
Guard probes là known regression/publication-policy, không held-out.

## Numeric gold

Chỉ hỏi tiền cho một hành vi và nói rõ ô tô thông thường, không gây tai nạn.
Không suy điểm từ tiền và không khẳng định "không bị trừ điểm" khi không hỏi.
Mỗi case có hai ý: phạm vi biên áp dụng và mức tiền từ clause head, cùng stable
source reference/text/context hash. Validator đối chiếu khoảng và mức tiền
với đúng chunk frozen, không chỉ tin đáp án từ labels.json.

Đối chiếu bổ sung với
[toàn văn 168 trên Cổng Chính phủ](https://xaydungchinhsach.chinhphu.vn/toan-van-nghi-dinh-168-2024-nd-cp-quy-dinh-xu-phat-vi-pham-hanh-chinh-ve-trat-tu-atgt-duong-bo-119241231164556785.htm),
Điều 6 khoản 3/5/6. Evidence/gold vẫn lấy từ snapshot, không nhập trang web vào
corpus. Ba leaf dùng ở đây không có amendment operation; không đổi citation
thành "238 thay thế 168" hoặc dùng một dự thảo sửa nghị định làm nguồn luật.

## Guard probes không phải kết luận luật tương lai

Query hỏi có thể dùng đúng đoạn được cung cấp để kết luận chắc chắn tại ngày
đã nêu hay không. Mode `publication_guard_probe` kiểm tra fail-closed của frozen
evidence bundle, không kiểm tra mức phạt thực tế năm 2028/2029.

- Mọi reference của locator blocked mang `role=context`, không positive support.
- Tại cutoff cũng không gỡ block vì review chung đã approved.
- Ngày trước/đúng/sau mốc không tự đổi temporal status/publication eligibility
  đã freeze. Query date, boundary anchor và legal_as_of được lưu riêng.
- Mixed không được mô tả là future toàn bộ. Repealed placeholder không cung
  cấp nội dung cũ để trả lời một vụ việc lịch sử.
- Nêu thiếu căn cứ đã duyệt cho phạm vi/ngày; không suy "không phạt", quy định
  cũ tiếp tục áp dụng, hoặc toàn Điều không còn nghĩa vụ.
- Mốc được lấy từ `temporal_rules.effective_from > legal_as_of`, không đặt lịch
  mới hoặc sửa các metadata nguồn. Ba placeholder chỉ probe tại cutoff, không
  giả source còn nội dung trước ngày bãi bỏ.

Guard gold có uncertainty/temporal facet unknown, context locator và abstain
expectation. Đây là nhãn policy của hệ thống bị giới hạn, không khẳng định
pháp luật không có câu trả lời. Blocked evidence không lọt vào positive replay.

## Technical audit và human review khác nhau

Tool `evaluation.development_dataset` kiểm tra parent design byte-exact (bao
gồm frozen gold/source/snapshot), schema, source/reference/context hashes,
numeric membership/money, blocked context, đủ locator/mốc và các review groups.
`technical_audit.json` ghi phép kiểm và counts; không ghi các stage/model pass.

`REVIEW.md` gom 7 mục để owner duyệt nội dung:

1. bốn tình huống numeric mới;
2. hai conversation mới;
3. một mục quyết định dùng các câu/đáp án giữ nguyên từ 50 gold và policy
   fail-closed đã chốt, gồm các fixtures kỹ thuật/guard liên quan.

Mỗi nhóm liệt kê case IDs và checksum nội dung được duyệt. Approval theo nhóm
chỉ hợp lệ sau khi owner xác nhận đúng phạm vi; **không** tự biến các kiểm tra
kỹ thuật, approval cũ hoặc "tiến hành đi" thành approval của 54 case mới.
Owner không phải kiểm code/pool/hash; có thể mở TECHNICAL.md/EVIDENCE.md khi muốn
đối chiếu. Đáp án, ý bắt buộc, full source/context và caveat có sẵn để review,
không chỉ một bảng tiền thiếu căn cứ. Không tự giả chuyên môn luật sư của owner.

Sau approval cần dataset version riêng có review record, receipt và gate phù
hợp. Nếu reviewer sửa nội dung/gold, tạo version mới; không sửa source/receipt
đã freeze để hợp thức hóa. C0–C4 và production publication rules vẫn giữ nguyên.

## Held-out

Held-out vẫn chưa author/sealed. Không tạo nó trong context đang chỉnh hệ thống
rồi gọi unseen. Giữ blueprint và exposure inventory; giải quyết custody/author/
reviewer ngoài tuning workspace ở bước riêng. Development packet hoàn thiện
về authoring/technical audit không đồng nghĩa Pha 3 đầy đủ hoặc benchmark ready.
