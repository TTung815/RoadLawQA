# Pilot protocol — 10 candidate

Pilot chạy trước full build, cùng schema và snapshot evidence gate.
Kết quả: schema/provenance đạt; chưa independent legal approval, chưa chạy model.

Findings đã áp dụng vào protocol/full audit:

- Câu 1 bỏ số hiệu khỏi query tự nhiên; số hiệu nằm trong evidence.
- Câu 2 giữ definition; không ép tất cả query thành scenario.
- Câu 5 tiền và điểm cần hai leaf, hai facet riêng.
- Câu 7 thêm rõ xe gia đình; giữ quy tắc/ngoại lệ và amendment provenance.
- Câu 9 giữ ngày 2025; cutoff snapshot không chứng minh lịch sử, expected abstain.
- Câu 16 giữ thiếu dữ kiện có chủ đích để kiểm tra conditional/exception.
- Câu 23 có căn cứ từng hành vi và nguyên tắc trừ điểm, nhưng tổng hợp tiền cần dependency.
- Câu 36 đóng hai đầu khoảng số; mức tiền không tự chứng minh mức điểm.
- Câu 43 tuổi lái xe và tuổi chịu xử phạt khác nhau; không suy mức tiền từ nguồn tuổi lái xe.
- Câu 48 thiếu tình trạng phanh/lái và cảnh báo; phải nêu điều kiện, không khẳng định hợp pháp.
- Leaf context có mức tiền/giới hạn số người; lưu full enriched context và hash để review.

## Câu 01 — edit

- Gốc: Theo Luật Trật tự, an toàn giao thông đường bộ (Luật 36/2024/QH15), hành vi điều khiển xe khi trong máu hoặc hơi thở có nồng độ cồn có bị nghiêm cấm không?
- Query audit: Người điều khiển phương tiện giao thông đường bộ có bị nghiêm cấm điều khiển phương tiện khi trong máu hoặc hơi thở có nồng độ cồn không?
- Lý do: Bỏ số hiệu luật và câu dẫn nguồn để kiểm tra tìm căn cứ từ câu hỏi tự nhiên; giữ hành vi gốc.
- Loại/family: factual / historical_001
- Tags: direct, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Có. Hành vi điều khiển phương tiện tham gia giao thông đường bộ mà trong máu hoặc hơi thở có nồng độ cồn thuộc các hành vi bị nghiêm cấm, theo khoản 2 Điều 9 của văn bản hợp nhất 55/VBHN-VPQH. Câu này chỉ hỏi quy tắc cấm, không hỏi ngưỡng xử phạt.

Required facets:

- f1 [rule/positive_support]: Xác định đúng hành vi bị cấm; không biến ngưỡng xử phạt thành ngưỡng được phép. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d9-k2` — khoản 2 Điều 9 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 02 — keep

- Gốc: Kết cấu hạ tầng đường bộ bao gồm những gì?
- Query audit: Kết cấu hạ tầng đường bộ bao gồm những gì?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / historical_002
- Tags: definition, direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Kết cấu hạ tầng đường bộ gồm công trình đường bộ; bến xe; bãi đỗ xe; trạm dừng nghỉ; điểm dừng xe, đỗ xe; đất của đường bộ; hành lang an toàn đường bộ và các công trình phụ trợ phục vụ cho hoạt động đường bộ (khoản 4 Điều 2, 49/VBHN-VPQH).

Required facets:

- f1 [definition/positive_support]: Nêu đủ các thành phần của kết cấu hạ tầng đường bộ, không chỉ liệt kê đường/cầu. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d2-k4` — khoản 4 Điều 2 49/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 05 — edit

- Gốc: Hành vi dùng tay cầm và sử dụng điện thoại khi đang điều khiển xe ô tô di chuyển trên đường bị xử phạt như thế nào (mức phạt tiền và trừ điểm)?
- Query audit: Người lái ô tô dùng tay cầm và sử dụng điện thoại khi xe đang di chuyển trên đường, không gây tai nạn, bị phạt bao nhiêu tiền và trừ bao nhiêu điểm giấy phép lái xe?
- Lý do: Bỏ gợi ý thuật ngữ và thêm rõ không gây tai nạn để cô lập nhánh thông thường; không suy đây là dữ kiện gốc.
- Loại/family: penalty / historical_005
- Tags: money, license_points, multiple_facets, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Với hành vi và điều kiện đã nêu: phạt 4.000.000–6.000.000 đồng (điểm h khoản 5 Điều 6) và trừ 04 điểm GPLX (điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP). Cần dẫn cả leaf hành vi và leaf trừ điểm.

Required facets:

- f1 [money/positive_support]: Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển. (groups: g1)
- f2 [license_points/positive_support]: Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k5-ph` — điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k5-ph` — điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k16-pb` — điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 07 — edit

- Gốc: Tôi lái xe ô tô 5 chỗ, con tôi 9 tuổi, cao 1m3. Tôi có được cho con tôi ngồi ở ghế phụ (cùng hàng ghế với người lái xe) không?
- Query audit: Tôi lái ô tô gia đình 5 chỗ, không kinh doanh vận tải, chở con 9 tuổi cao 1,30 m. Tôi có được cho con ngồi cùng hàng ghế với người lái không và phải dùng thiết bị an toàn nào?
- Lý do: Làm rõ xe gia đình và bổ sung facet thiết bị an toàn để đánh giá cả điều kiện, ngoại lệ và sửa đổi; không hỏi tiền phạt.
- Loại/family: scenario / historical_007
- Tags: amended_rule, condition, exception, multiple_facets
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Theo khoản 3 Điều 10 của 55/VBHN-VPQH tại cutoff, trẻ vừa dưới 10 tuổi vừa cao dưới 1,35 m không được ngồi cùng hàng ghế với người lái, trừ ô tô chỉ có một hàng ghế. Xe gia đình 5 chỗ trong câu không thuộc ngoại lệ một hàng ghế; người lái phải sử dụng, hướng dẫn sử dụng thiết bị an toàn phù hợp cho trẻ. Ngoại lệ xe kinh doanh vận tải hành khách đối với thiết bị không áp dụng dữ kiện đã nêu.

Required facets:

- f1 [condition/positive_support]: Hai điều kiện tuổi và chiều cao đồng thời: 9<10 và 1,30<1,35. (groups: g1)
- f2 [rule/positive_support]: Không xếp trẻ ngồi cùng hàng ghế người lái; có ngoại lệ xe chỉ một hàng ghế. (groups: g2)
- f3 [exception/positive_support]: Nghĩa vụ thiết bị phù hợp và ngoại lệ xe kinh doanh vận tải hành khách, không áp dụng xe gia đình. (groups: g3)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d10-k3` — khoản 3 Điều 10 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `55-vbhn-vpqh-d10-k3` — khoản 3 Điều 10 55/VBHN-VPQH; eligible=True; operations=none
- g3/support: `55-vbhn-vpqh-d10-k3` — khoản 3 Điều 10 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 09 — keep

- Gốc: Giấy phép lái xe của tôi có 12 điểm. Ngày 01/02/2025 tôi bị trừ 2 điểm. Nếu sau đó tôi không vi phạm gì thêm, khi nào giấy phép lái xe của tôi được phục hồi đủ 12 điểm?
- Query audit: Giấy phép lái xe của tôi có 12 điểm. Ngày 01/02/2025 tôi bị trừ 2 điểm. Nếu sau đó tôi không vi phạm gì thêm, khi nào giấy phép lái xe của tôi được phục hồi đủ 12 điểm?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / license_point_recovery
- Tags: explicit_date, temporal_gap
- Expectation: abstain; coverage=insufficient; allowed=insufficient_evidence
- Temporal: explicit_date; cutoff=2026-09-22; explicit_date=2025-02-01
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Câu nêu lần trừ điểm ngày 01/02/2025. Snapshot hiện hành 22/09/2026 không phải snapshot lịch sử đã xác minh cho ngày đó; chưa thể chốt ngày phục hồi cho vụ việc năm 2025 bằng corpus này. Có thể nêu quy tắc hiện hành về GPLX chưa bị trừ hết điểm và 12 tháng không bị trừ điểm, nhưng không tự áp ngược rồi kết luận ngày 01/02/2026.

Required facets:

- f1 [temporal/unknown]: Nhận diện ngày lịch sử 01/02/2025 ngoài phạm vi replay đã xác minh; không suy ngược quy tắc hiện hành. (groups: none)
- f2 [uncertainty/unknown]: Chỉ dùng quy tắc 12 tháng hiện hành làm context, không làm căn cứ chốt vụ việc lịch sử. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g2/context: `55-vbhn-vpqh-d58-k2` — khoản 2 Điều 58 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer cần snapshot/temporal provenance cho 2025 nếu muốn chuyển expectation khỏi abstain; không dùng Pha 0 làm current-law gold.

## Câu 16 — keep

- Gốc: Người lái xe mô tô hai bánh chở theo 2 người trên xe thì có bị phạt không?
- Query audit: Người lái xe mô tô hai bánh chở theo 2 người trên xe thì có bị phạt không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / motorcycle_passengers
- Tags: missing_facts, exception, multi_locator
- Expectation: conditional; coverage=conditional; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Cần biết hai người được chở thuộc trường hợp nào. Quy tắc là chỉ chở một người, nhưng được chở tối đa hai người trong các trường hợp người bệnh đi cấp cứu, áp giải người vi phạm, trẻ em dưới 12 tuổi, người già yếu/người khuyết tật. Nhánh chở hai người không thuộc ngoại lệ có mức phạt 400.000–600.000 đồng. Không chốt người trong câu bị phạt khi chưa biết ngoại lệ.

Required facets:

- f1 [rule/positive_support]: Quy tắc chở một người và tối đa hai người ở ngoại lệ, đọc cả clause head. (groups: g1)
- f2 [money/positive_support]: Nhánh không ngoại lệ: 400.000–600.000 đồng. (groups: g2)
- f3 [uncertainty/unknown]: Chưa biết tuổi/tình trạng/lý do chở hai người; không gán một nhánh. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d33-k1-pa` — điểm a khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d33-k1-pb` — điểm b khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d33-k1-pc` — điểm c khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d33-k1-pd` — điểm d khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k2-pg` — điểm g khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 23 — edit

- Gốc: Tôi lái xe ô tô vượt đèn đỏ và dùng tay cầm điện thoại di động cùng lúc. Tôi bị xử phạt tổng hợp như thế nào?
- Query audit: Tôi lái ô tô vượt đèn đỏ và đồng thời dùng tay cầm, sử dụng điện thoại khi xe đang di chuyển. Tôi không gây tai nạn và không có hiệu lệnh khác cho phép đi. Nếu hai hành vi bị xử phạt trong cùng một lần, tiền phạt tổng hợp và điểm giấy phép lái xe được tính thế nào?
- Lý do: Làm rõ hai hành vi, hậu quả và cùng lần xử phạt; giữ bài toán tổng hợp thay vì rút thành hai câu tra cứu.
- Loại/family: scenario / historical_023
- Tags: missing_dependency, multiple_facets, multi_locator
- Expectation: abstain; coverage=insufficient; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Trong snapshot, có căn cứ cho từng hành vi: vượt đèn đỏ ở ô tô phạt 18–20 triệu đồng, dùng tay cầm và sử dụng điện thoại phạt 4–6 triệu đồng; mỗi hành vi thuộc nhánh trừ 04 điểm. Nếu cùng lần xử phạt và có từ hai hành vi bị trừ điểm, chỉ áp dụng hành vi bị trừ nhiều điểm nhất, không cộng điểm. Tuy nhiên, để chốt tiền phạt tổng hợp và các nguyên tắc xử phạt nhiều hành vi cần dependency Luật Xử lý vi phạm hành chính chưa ingest; không tự cộng khoảng thành đáp án đầy đủ.

Required facets:

- f1 [money/positive_support]: Có mức tiền riêng từng hành vi 18–20 và 4–6 triệu, không tự chứng minh nguyên tắc tổng hợp. (groups: g1)
- f2 [license_points/positive_support]: Cùng lần: chọn hành vi bị trừ nhiều điểm nhất; liên kết 04 điểm cho hai hành vi. (groups: g2)
- f3 [uncertainty/unknown]: Thiếu dependency cho phép chốt tiền phạt tổng hợp. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k9-pb` — điểm b khoản 9 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g1/support: `nd168-effective-as-of-2026-09-22-d6-k5-ph` — điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k16-pb` — điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d50-k1-pb` — điểm b khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Dependency chưa có:

- Luật Xử lý vi phạm hành chính: nguyên tắc xử phạt nhiều hành vi và xác định tiền phạt tổng hợp.

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 36 — edit

- Gốc: Người điều khiển xe ô tô chạy quá tốc độ quy định từ 10 km/h đến 20 km/h bị xử phạt bao nhiêu tiền?
- Query audit: Người lái ô tô chạy quá tốc độ quy định từ 10 km/h đến 20 km/h, không gây tai nạn, bị phạt bao nhiêu tiền?
- Lý do: Nêu rõ không gây tai nạn để chọn nhánh thông thường, giữ hai mốc 10 và 20 cho bài khoảng số.
- Loại/family: penalty / car_speed_10_20
- Tags: money, numeric, boundary
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 4.000.000–6.000.000 đồng tại điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP. Khoảng từ 10 đến 20 km/h giữ cả hai đầu mút; không gán mức trên 20 cho đúng mốc 20.

Required facets:

- f1 [money/positive_support]: 4–6 triệu đồng cho toàn khoảng 10–20 km/h của ô tô. (groups: g1)
- f2 [reasoning/positive_support]: Giữ biên 10 và 20; không trộn khoảng trên 20. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k5-pđ` — điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k5-pđ` — điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 43 — keep

- Gốc: Con trai tôi năm nay 13 tuổi, cháu lấy trộm chìa khóa xe máy (xe ga 110cc) của gia đình để chạy đi chơi và bị công an giữ lại. Xin hỏi ở độ tuổi này cháu bị phạt tiền bao nhiêu?
- Query audit: Con trai tôi năm nay 13 tuổi, cháu lấy trộm chìa khóa xe máy (xe ga 110cc) của gia đình để chạy đi chơi và bị công an giữ lại. Xin hỏi ở độ tuổi này cháu bị phạt tiền bao nhiêu?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_043
- Tags: missing_dependency, reasoning
- Expectation: abstain; coverage=insufficient; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Không đủ nguồn để xác định mức phạt tiền của người 13 tuổi. Điều kiện tuổi lái xe trong luật giao thông và tuổi/chủ thể chịu xử phạt hành chính là hai vấn đề khác nhau. Cần dependency Luật Xử lý vi phạm hành chính đã được duyệt trước khi chốt mức tiền hoặc kết luận không bị phạt. Không suy từ chưa đủ tuổi lái xe thành một mức phạt tiền cho trẻ.

Required facets:

- f1 [uncertainty/unknown]: Nhận diện thiếu dependency về tuổi chịu xử phạt; không công bố con số/không phạt. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):


Dependency chưa có:

- Luật Xử lý vi phạm hành chính: tuổi, chủ thể chịu xử phạt và hình thức xử phạt người chưa thành niên.

Điểm reviewer cần chốt:

- Duyệt scope dependency về người chưa thành niên; phân biệt lái 110 cm³, tuổi được lái và trách nhiệm của trẻ/chủ xe.

## Câu 48 — keep

- Gốc: Xe ô tô của tôi bị chết máy giữa đường. Tôi nhờ một người bạn lái xe bán tải dùng dây cáp mềm để kéo xe tôi về gara sửa chữa. Việc này có đúng luật không?
- Query audit: Xe ô tô của tôi bị chết máy giữa đường. Tôi nhờ một người bạn lái xe bán tải dùng dây cáp mềm để kéo xe tôi về gara sửa chữa. Việc này có đúng luật không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_048
- Tags: missing_facts, condition, multi_locator
- Expectation: conditional; coverage=conditional; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Cần biết hệ thống phanh/lái còn hiệu lực, có người điều khiển xe được kéo, nối chắc chắn/an toàn và biển/đèn cảnh báo. Khoản 1 Điều 29 của 55/VBHN-VPQH yêu cầu nếu hệ thống hãm không còn hiệu lực thì phải nối bằng thanh cứng; đồng thời có người điều khiển, hệ thống lái còn hiệu lực, biển và đèn cảnh báo phù hợp. Dữ kiện chỉ có cáp mềm và chết máy chưa đủ kết luận việc kéo xe hợp pháp.

Required facets:

- f1 [condition/positive_support]: Đủ người điều khiển, hệ thống lái, nối an toàn, điều kiện thanh cứng và cảnh báo. (groups: g1)
- f2 [uncertainty/unknown]: Thiếu tình trạng phanh/lái, người điều khiển và cảnh báo. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d29-k1-pa` — điểm a khoản 1 Điều 29 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d29-k1-pb` — điểm b khoản 1 Điều 29 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d29-k1-pc` — điểm c khoản 1 Điều 29 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

