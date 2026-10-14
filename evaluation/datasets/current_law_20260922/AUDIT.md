# Audit 50 historical candidates — current-law draft

Cutoff: 2026-09-22. Audit date: 2026-10-09. Snapshot: `roadlawqa-current-law-2026-09-22`.

Technical integrity đạt; **0 gold được phê duyệt**. Chưa chạy model/C0–C4.
CSV gốc giữ nguyên. Tất cả query dẫn xuất vẫn historically_used/legacy.

| Chỉ số | Kết quả |
| --- | --- |
| Candidate audited | 50 |
| Giữ / sửa / loại | 18 / 32 / 0 |
| Publish / conditional / abstain (draft) | 40 / 5 / 5 |
| Gold approved | 0 |
| Evidence chunks | 67 |

## Bảng quyết định

| ID | Decision | Type | Expectation | Family | Pilot |
| --- | --- | --- | --- | --- | --- |
| 01 | edit | factual | publish | historical_001 | yes |
| 02 | keep | factual | publish | historical_002 | yes |
| 03 | edit | penalty | publish | historical_003 |  |
| 04 | edit | factual | publish | historical_004 |  |
| 05 | edit | penalty | publish | historical_005 | yes |
| 06 | keep | factual | publish | historical_006 |  |
| 07 | edit | scenario | publish | historical_007 | yes |
| 08 | edit | scenario | publish | historical_008 |  |
| 09 | keep | scenario | abstain | license_point_recovery | yes |
| 10 | keep | scenario | abstain | license_point_recovery |  |
| 11 | edit | factual | publish | historical_011 |  |
| 12 | keep | factual | publish | historical_012 |  |
| 13 | keep | penalty | publish | historical_013 |  |
| 14 | keep | penalty | publish | historical_014 |  |
| 15 | edit | factual | publish | historical_015 |  |
| 16 | keep | factual | conditional | motorcycle_passengers | yes |
| 17 | edit | penalty | publish | historical_017 |  |
| 18 | edit | factual | publish | historical_018 |  |
| 19 | edit | penalty | publish | historical_019 |  |
| 20 | edit | penalty | publish | expressway_reverse_direction |  |
| 21 | edit | factual | publish | historical_021 |  |
| 22 | edit | penalty | publish | historical_022 |  |
| 23 | edit | scenario | abstain | historical_023 | yes |
| 24 | edit | penalty | publish | historical_024 |  |
| 25 | edit | penalty | publish | historical_025 |  |
| 26 | edit | scenario | publish | historical_026 |  |
| 27 | edit | scenario | publish | historical_027 |  |
| 28 | edit | penalty | publish | historical_028 |  |
| 29 | keep | scenario | abstain | historical_029 |  |
| 30 | keep | scenario | publish | historical_030 |  |
| 31 | keep | factual | publish | historical_031 |  |
| 32 | edit | factual | publish | historical_032 |  |
| 33 | keep | factual | publish | historical_033 |  |
| 34 | edit | factual | publish | historical_034 |  |
| 35 | edit | factual | publish | historical_035 |  |
| 36 | edit | penalty | publish | car_speed_10_20 | yes |
| 37 | keep | penalty | publish | historical_037 |  |
| 38 | edit | penalty | publish | expressway_reverse_direction |  |
| 39 | edit | penalty | publish | historical_039 |  |
| 40 | edit | penalty | publish | historical_040 |  |
| 41 | edit | scenario | publish | historical_041 |  |
| 42 | keep | scenario | conditional | historical_042 |  |
| 43 | keep | scenario | abstain | historical_043 | yes |
| 44 | edit | scenario | conditional | historical_044 |  |
| 45 | edit | scenario | publish | car_speed_10_20 |  |
| 46 | keep | scenario | conditional | historical_046 |  |
| 47 | edit | scenario | publish | historical_047 |  |
| 48 | keep | scenario | conditional | historical_048 | yes |
| 49 | edit | scenario | publish | historical_049 |  |
| 50 | keep | scenario | publish | motorcycle_passengers |  |

Gap/giới hạn:

- No unseen held-out cases; revised historical questions remain exposed.
- No multi-turn cases or complete temporal boundary suite for 2028/2029.
- No independent legal gold review; pilot only checks schema/provenance.
- Missing dependencies and negative-support provenance intentionally remain blocked.

## Ma trận coverage thực tế

| Tag | Số case |
| --- | --- |
| additional_sanction | 1 |
| amended_rule | 2 |
| boundary | 4 |
| condition | 14 |
| cross_document | 7 |
| definition | 8 |
| direct | 8 |
| exception | 10 |
| explicit_date | 4 |
| license_points | 4 |
| missing_dependency | 2 |
| missing_facts | 5 |
| money | 21 |
| multi_locator | 13 |
| multiple_facets | 7 |
| negative_conclusion | 2 |
| numeric | 11 |
| reasoning | 6 |
| rule | 1 |
| source_cue_removed | 6 |
| temporal_gap | 1 |

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

## Câu 03 — edit

- Gốc: Người điều khiển xe ô tô không thắt dây đai an toàn khi xe đang chạy bị phạt bao nhiêu tiền?
- Query audit: Người điều khiển xe ô tô không thắt dây đai an toàn khi xe đang chạy trên đường bị phạt bao nhiêu tiền?
- Lý do: Làm rõ phạm vi đang chạy trên đường để khớp hành vi, giữ mục tiêu mức tiền của người lái.
- Loại/family: penalty / historical_003
- Tags: money, direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Người lái ô tô không thắt dây đai an toàn khi điều khiển xe chạy trên đường bị phạt từ 800.000 đến 1.000.000 đồng, theo điểm k khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP trong snapshot. Không suy từ câu trả lời mức tiền rằng mọi chế tài khác đều không áp dụng.

Required facets:

- f1 [money/positive_support]: Đúng chủ thể người lái và khoảng 800.000–1.000.000 đồng. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k3-pk` — điểm k khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 04 — edit

- Gốc: Theo luật mới, giấy phép lái xe hạng A1 cấp cho người lái xe mô tô hai bánh có dung tích xi-lanh đến bao nhiêu cm³?
- Query audit: Giấy phép lái xe hạng A1 cấp mới theo quy định tại ngày 22/09/2026 cho phép lái xe mô tô hai bánh có dung tích xi-lanh tối đa bao nhiêu cm³?
- Lý do: Thay 'luật mới' bằng ngày cố định và làm rõ cấp mới, không lẫn GPLX cũ theo chuyển tiếp.
- Loại/family: factual / historical_004
- Tags: numeric, explicit_date
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: explicit_date; cutoff=2026-09-22; explicit_date=2026-09-22
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Hạng A1 cấp cho người lái xe mô tô hai bánh có dung tích xi-lanh đến 125 cm³; trường hợp động cơ điện có công suất đến 11 kW. Căn cứ điểm a khoản 1 Điều 57, 55/VBHN-VPQH. Không dùng kết luận này để tự chuyển đổi quyền lái của GPLX A1 cấp theo quy định cũ.

Required facets:

- f1 [rule/positive_support]: Giới hạn đến 125 cm³, bao gồm mốc 125, đúng phạm vi GPLX cấp mới. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d57-k1-pa` — điểm a khoản 1 Điều 57 55/VBHN-VPQH; eligible=True; operations=none

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

## Câu 06 — keep

- Gốc: Việc thu tiền sử dụng đường bộ trên đường cao tốc có bắt buộc phải thực hiện theo hình thức điện tử không dừng không?
- Query audit: Việc thu tiền sử dụng đường bộ trên đường cao tốc có bắt buộc phải thực hiện theo hình thức điện tử không dừng không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / historical_006
- Tags: direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Có. Khoản 3 Điều 43 của 49/VBHN-VPQH quy định thanh toán tiền sử dụng đường bộ trên đường cao tốc phải thực hiện theo hình thức điện tử không dừng. Không mở rộng thành mọi loại khoản thu ở mọi tuyến đường.

Required facets:

- f1 [rule/positive_support]: Đúng phạm vi thanh toán tiền sử dụng đường bộ trên đường cao tốc và hình thức điện tử không dừng. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d43-k3` — khoản 3 Điều 43 49/VBHN-VPQH; eligible=True; operations=none

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

## Câu 08 — edit

- Gốc: Anh A điều khiển xe máy vượt đèn đỏ (không chấp hành hiệu lệnh của đèn tín hiệu giao thông) và bị Cảnh sát giao thông dừng xe. Anh A sẽ bị xử phạt như thế nào (phạt tiền và trừ điểm)?
- Query audit: Một người lái xe mô tô vượt đèn đỏ trên đường, không có hiệu lệnh khác cho phép đi và không gây tai nạn. Người đó bị phạt tiền và trừ điểm giấy phép lái xe như thế nào?
- Lý do: Chuẩn hóa xe máy thành xe mô tô và nêu điều kiện loại trừ nhánh tai nạn/hiệu lệnh ưu tiên.
- Loại/family: scenario / historical_008
- Tags: money, license_points, multiple_facets, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Không chấp hành hiệu lệnh đèn tín hiệu giao thông ở nhánh đã nêu: phạt 4.000.000–6.000.000 đồng theo điểm c khoản 7 Điều 7 và trừ 04 điểm GPLX theo điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [money/positive_support]: Đúng nhánh xe mô tô: 4–6 triệu đồng. (groups: g1)
- f2 [license_points/positive_support]: 04 điểm, không nhầm điểm của ô tô hoặc nhánh tai nạn. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d7-k7-pc` — điểm c khoản 7 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k7-pc` — điểm c khoản 7 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k13-pb` — điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

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

## Câu 10 — keep

- Gốc: Tôi bị Cảnh sát giao thông lập biên bản xử phạt và thông báo bị trừ 2 điểm giấy phép lái xe. Tôi đã ra kho bạc nộp phạt xong xuôi vào ngày hôm sau. Vậy 2 điểm bị trừ đó có được cộng lại (hoàn trả) ngay lập tức sau khi tôi đóng tiền không?
- Query audit: Tôi bị Cảnh sát giao thông lập biên bản xử phạt và thông báo bị trừ 2 điểm giấy phép lái xe. Tôi đã ra kho bạc nộp phạt xong xuôi vào ngày hôm sau. Vậy 2 điểm bị trừ đó có được cộng lại (hoàn trả) ngay lập tức sau khi tôi đóng tiền không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / license_point_recovery
- Tags: negative_conclusion, multi_locator
- Expectation: abstain; coverage=insufficient; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Không đủ provenance để công bố một kết luận âm đầy đủ theo policy V2 hiện tại. Phần có căn cứ: trừ điểm gắn với hiệu lực quyết định xử phạt; phục hồi đủ 12 điểm hiện hành cần GPLX chưa bị trừ hết điểm và 12 tháng không bị trừ điểm kể từ lần gần nhất. Nộp tiền phạt và phục hồi điểm là hai cơ chế cần phân biệt; không tự hứa cộng lại điểm sau nộp tiền.

Required facets:

- f1 [rule/positive_support]: Phân biệt cơ chế trừ/khôi phục điểm và thời điểm quyết định có hiệu lực. (groups: g1)
- f2 [uncertainty/unknown]: Kết luận phủ định hoàn trả ngay cần reviewer xác nhận provenance theo policy negative-support. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d50-k1-pa` — điểm a khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d58-k2` — khoản 2 Điều 58 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Xem liệu quy tắc dương về thời hạn đã đủ trả lời phủ định cụ thể mà không nới contract negative-support; hiện draft giữ abstain.

## Câu 11 — edit

- Gốc: Giấy phép lái xe hạng B có thời hạn bao nhiêu năm?
- Query audit: Giấy phép lái xe hạng B cấp mới theo quy định tại ngày 22/09/2026 có thời hạn bao nhiêu năm kể từ ngày cấp?
- Lý do: Làm rõ cấp mới và điểm bắt đầu tính thời hạn, không suy từ hạng B cũ/chuyển tiếp.
- Loại/family: factual / historical_011
- Tags: numeric, explicit_date
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: explicit_date; cutoff=2026-09-22; explicit_date=2026-09-22
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

GPLX hạng B có thời hạn 10 năm kể từ ngày cấp, theo điểm b khoản 5 Điều 57, 55/VBHN-VPQH.

Required facets:

- f1 [rule/positive_support]: 10 năm và tính kể từ ngày cấp; đúng phạm vi GPLX cấp mới. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d57-k5-pb` — điểm b khoản 5 Điều 57 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 12 — keep

- Gốc: Khi nào người lái xe ô tô phải bật đèn chiếu sáng phía trước?
- Query audit: Khi nào người lái xe ô tô phải bật đèn chiếu sáng phía trước?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / historical_012
- Tags: condition, multiple_facets
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phải bật đèn chiếu sáng phía trước từ 18 giờ ngày hôm trước đến 06 giờ ngày hôm sau, hoặc khi sương mù, khói, bụi, trời mưa, thời tiết xấu làm hạn chế tầm nhìn (khoản 1 Điều 20, 55/VBHN-VPQH). Hai căn cứ thời gian và hạn chế tầm nhìn là các nhánh thay thế, không đòi đồng thời.

Required facets:

- f1 [condition/positive_support]: Mốc 18h–06h hoặc điều kiện hạn chế tầm nhìn; giữ đúng quan hệ hoặc. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d20-k1` — khoản 1 Điều 20 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 13 — keep

- Gốc: Người điều khiển xe mô tô chạy quá tốc độ quy định 15 km/h bị phạt bao nhiêu tiền?
- Query audit: Người điều khiển xe mô tô chạy quá tốc độ quy định 15 km/h bị phạt bao nhiêu tiền?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: penalty / historical_013
- Tags: money, numeric, boundary
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Vượt tốc độ 15 km/h thuộc khoảng từ 10 đến 20 km/h: phạt 800.000–1.000.000 đồng đối với người lái xe mô tô tại điểm a khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP. Đây là câu mức tiền, không suy về mọi chế tài khác.

Required facets:

- f1 [reasoning/positive_support]: 15 nằm trong khoảng từ 10 đến 20 km/h. (groups: g1)
- f2 [money/positive_support]: 800.000–1.000.000 đồng, đúng xe mô tô. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d7-k4-pa` — điểm a khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k4-pa` — điểm a khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 14 — keep

- Gốc: Hành vi đi xe máy dàn hàng ngang từ 3 xe trở lên bị phạt bao nhiêu tiền?
- Query audit: Hành vi đi xe máy dàn hàng ngang từ 3 xe trở lên bị phạt bao nhiêu tiền?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: penalty / historical_014
- Tags: money, numeric
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Điều khiển xe mô tô, xe gắn máy chạy dàn hàng ngang từ 03 xe trở lên bị phạt 600.000–800.000 đồng theo điểm k khoản 3 Điều 7 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [money/positive_support]: Giữ điều kiện từ 03 xe trở lên và mức 600.000–800.000 đồng. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d7-k3-pk` — điểm k khoản 3 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 15 — edit

- Gốc: Theo Luật Đường bộ, đường tỉnh là gì?
- Query audit: Đường tỉnh được định nghĩa như thế nào?
- Lý do: Bỏ câu dẫn tên luật để đánh giá tự tìm nguồn và nội dung định nghĩa đã sửa.
- Loại/family: factual / historical_015
- Tags: definition, amended_rule, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Đường tỉnh là đường nằm trong địa bàn một tỉnh nối trung tâm hành chính của tỉnh với trung tâm hành chính của cấp xã; đường có vị trí quan trọng đối với sự phát triển kinh tế–xã hội của tỉnh, theo điểm b khoản 1 Điều 8, 49/VBHN-VPQH. Không giữ phần định nghĩa cấp huyện của đáp án cũ.

Required facets:

- f1 [definition/positive_support]: Định nghĩa cấp xã theo nội dung hợp nhất tại cutoff, không lẫn cấp huyện. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d8-k1-pb` — điểm b khoản 1 Điều 8 49/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

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

## Câu 17 — edit

- Gốc: Người đi bộ đi vào đường cao tốc bị phạt bao nhiêu tiền?
- Query audit: Một người đi bộ không làm nhiệm vụ quản lý hoặc bảo trì đường cao tốc đi vào đường cao tốc thì bị phạt bao nhiêu tiền?
- Lý do: Thêm điều kiện loại trừ ngoại lệ quản lý/bảo trì để câu mức tiền có đáp án xác định.
- Loại/family: penalty / historical_017
- Tags: money, exception
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Với dữ kiện không thuộc ngoại lệ quản lý/bảo trì đường cao tốc, mức phạt 400.000–600.000 đồng theo điểm a khoản 2 Điều 10 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [money/positive_support]: 400.000–600.000 đồng cho người đi bộ; giữ ngoại lệ quản lý/bảo trì. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d10-k2-pa` — điểm a khoản 2 Điều 10 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 18 — edit

- Gốc: Hoạt động vận tải hành khách công cộng bằng xe buýt là gì?
- Query audit: Kinh doanh vận tải hành khách công cộng bằng xe buýt là gì và gồm những loại tuyến nào?
- Lý do: Chuẩn hóa đúng tên khái niệm và hỏi rõ cả nội tỉnh/liên tỉnh để kiểm tra toàn bộ định nghĩa.
- Loại/family: factual / historical_018
- Tags: definition, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Là loại hình kinh doanh dùng ô tô chở người từ 08 chỗ trở lên, không kể chỗ người lái, để vận tải hành khách; có điểm đầu, cuối, các điểm dừng đón/trả khách và lịch trình, hành trình xác định. Gồm tuyến nội tỉnh hoạt động trong một tỉnh/thành phố và liên tỉnh hoạt động từ hai tỉnh/thành phố trở lên, theo khoản 8 Điều 56, 49/VBHN-VPQH.

Required facets:

- f1 [definition/positive_support]: Đủ loại xe, số chỗ, điểm đầu/cuối/dừng và lịch trình/hành trình; đọc clause head đầy đủ. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d56-k8-pa` — điểm a khoản 8 Điều 56 49/VBHN-VPQH; eligible=True; operations=none
- g1/support: `49-vbhn-vpqh-d56-k8-pb` — điểm b khoản 8 Điều 56 49/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 19 — edit

- Gốc: Lái xe ô tô chở trẻ em mầm non mà xe không có thiết bị cảnh báo chống bỏ quên trẻ em thì bị phạt bao nhiêu tiền?
- Query audit: Người lái ô tô kinh doanh vận tải chở trẻ em mầm non, xe không có thiết bị có chức năng cảnh báo chống bỏ quên trẻ em, bị phạt bao nhiêu tiền?
- Lý do: Làm rõ kinh doanh vận tải để chọn Điều 27, không nhầm nhánh xe chở người thông thường.
- Loại/family: penalty / historical_019
- Tags: money, condition
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 3.000.000–5.000.000 đồng theo điểm b khoản 3 Điều 27 Nghị định 168/2024/NĐ-CP cho người lái ô tô kinh doanh vận tải thuộc phạm vi đã nêu.

Required facets:

- f1 [money/positive_support]: Đúng đối tượng ô tô kinh doanh vận tải chở trẻ và mức 3–5 triệu đồng. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d27-k3-pb` — điểm b khoản 3 Điều 27 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 20 — edit

- Gốc: Lái xe ô tô đi lùi xe trên đường cao tốc bị phạt bao nhiêu tiền và bị trừ bao nhiêu điểm?
- Query audit: Người lái ô tô thông thường, không phải xe ưu tiên đang làm nhiệm vụ khẩn cấp, lùi xe trên đường cao tốc bị phạt tiền và trừ điểm như thế nào?
- Lý do: Nêu rõ điều kiện loại trừ xe ưu tiên để có một nhánh áp dụng.
- Loại/family: penalty / expressway_reverse_direction
- Tags: money, license_points, exception, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 30.000.000–40.000.000 đồng theo điểm đ khoản 11 Điều 6 và trừ 10 điểm GPLX theo điểm d khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP. Giữ ngoại lệ xe ưu tiên làm nhiệm vụ khẩn cấp trong căn cứ.

Required facets:

- f1 [money/positive_support]: 30–40 triệu đồng, đúng hành vi lùi xe trên cao tốc. (groups: g1)
- f2 [license_points/positive_support]: 10 điểm liên kết đúng điểm đ khoản 11. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k11-pđ` — điểm đ khoản 11 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k11-pđ` — điểm đ khoản 11 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k16-pd` — điểm d khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 21 — edit

- Gốc: Theo Luật 36/2024, "Xe gắn máy" được định nghĩa như thế nào?
- Query audit: Xe gắn máy được định nghĩa như thế nào?
- Lý do: Bỏ số hiệu 36/2024, giữ mục tiêu định nghĩa tự nhiên.
- Loại/family: factual / historical_021
- Tags: definition, numeric, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Xe gắn máy là xe hai hoặc ba bánh chạy bằng động cơ, thiết kế/sản xuất để hoạt động trên đường bộ, vận tốc thiết kế không lớn hơn 50 km/h; động cơ nhiệt có dung tích làm việc hoặc tương đương không lớn hơn 50 cm³, động cơ điện không lớn hơn 04 kW; không bao gồm xe đạp máy. Căn cứ điểm g khoản 1 Điều 34, 55/VBHN-VPQH.

Required facets:

- f1 [definition/positive_support]: Đủ số bánh, vận tốc thiết kế, ngưỡng động cơ nhiệt/điện và loại trừ xe đạp máy. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d34-k1-pg` — điểm g khoản 1 Điều 34 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 22 — edit

- Gốc: Lái xe ô tô có tem kiểm định nhưng đã hết hạn 2 tháng bị phạt bao nhiêu tiền?
- Query audit: Người lái ô tô thuộc loại phải kiểm định, không phải xe đăng ký tạm thời, có tem kiểm định đã hết hạn 2 tháng, bị phạt bao nhiêu tiền?
- Lý do: Nêu rõ phạm vi phải kiểm định và ngoại lệ xe đăng ký tạm thời; không hỏi mức phạt chủ xe.
- Loại/family: penalty / historical_022
- Tags: money, numeric, boundary
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Hai tháng thuộc nhánh hết hiệu lực từ 01 tháng trở lên: người lái bị phạt 4.000.000–6.000.000 đồng theo điểm b khoản 6 Điều 13 Nghị định 168/2024/NĐ-CP. Không lẫn mức phạt của chủ phương tiện.

Required facets:

- f1 [money/positive_support]: 4–6 triệu đồng, nhánh từ 01 tháng trở lên và đúng chủ thể người lái. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d13-k6-pb` — điểm b khoản 6 Điều 13 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

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

## Câu 24 — edit

- Gốc: Một người đi xe đạp vào ban đêm nhưng không có đèn chiếu sáng hoặc tấm phản quang bị xử phạt như thế nào?
- Query audit: Một người đi xe đạp trên đường lúc 20 giờ, không sử dụng đèn và không có báo hiệu ở phía trước hoặc phía sau xe, bị phạt bao nhiêu tiền?
- Lý do: Thay 'ban đêm' bằng giờ cố định và mô tả chính xác thiếu đèn/báo hiệu; không tự đồng nhất tấm phản quang với mọi báo hiệu hợp lệ.
- Loại/family: penalty / historical_024
- Tags: money, condition, cross_document
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Thời gian 20 giờ thuộc 18h–06h. Xe thô sơ phải dùng đèn hoặc có báo hiệu phía trước và phía sau; nhánh vi phạm nêu trong câu bị phạt 100.000–200.000 đồng theo điểm i khoản 1 Điều 9 Nghị định 168/2024/NĐ-CP, cùng khoản 4 Điều 31 của 55/VBHN-VPQH.

Required facets:

- f1 [condition/positive_support]: Nhận diện thời gian và nghĩa vụ đèn/báo hiệu trước-sau. (groups: g1)
- f2 [money/positive_support]: 100.000–200.000 đồng cho xe đạp, không nhầm hầm đường bộ. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d31-k4` — khoản 4 Điều 31 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d9-k1-pi` — điểm i khoản 1 Điều 9 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 25 — edit

- Gốc: Lái xe máy "nẹt pô" (rú ga liên tục) trong khu dân cư bị phạt bao nhiêu tiền?
- Query audit: Người lái xe mô tô thông thường rú ga (nẹt pô) liên tục trong khu đông dân cư, không phải xe ưu tiên làm nhiệm vụ, bị phạt bao nhiêu tiền?
- Lý do: Chuẩn hóa khu dân cư thành phạm vi khu đông dân cư và loại trừ xe ưu tiên; giữ mục tiêu tiền phạt.
- Loại/family: penalty / historical_025
- Tags: money, condition, exception
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 8.000.000–10.000.000 đồng theo điểm k khoản 9 Điều 7 Nghị định 168/2024/NĐ-CP; giữ điều kiện liên tục, khu đông dân cư và ngoại lệ xe ưu tiên làm nhiệm vụ.

Required facets:

- f1 [money/positive_support]: 8–10 triệu đồng và đầy đủ điều kiện hành vi. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d7-k9-pk` — điểm k khoản 9 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 26 — edit

- Gốc: Luật 35/2024 (Điều 26) có nói về "tốc độ thiết kế" và "tốc độ khai thác" của đường bộ. Vậy khi Cảnh sát giao thông xử phạt lỗi chạy quá tốc độ, họ căn cứ vào tốc độ nào?
- Query audit: Khi xác định một xe chạy quá tốc độ cho phép trên đường, cần phân biệt tốc độ thiết kế và tốc độ khai thác như thế nào?
- Lý do: Bỏ gợi ý Điều 26/số hiệu luật; giữ mục tiêu phân biệt hai loại tốc độ, không yêu cầu thủ tục đo tốc độ ngoài corpus.
- Loại/family: scenario / historical_026
- Tags: definition, reasoning, cross_document
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Tốc độ thiết kế dùng tính chỉ tiêu kỹ thuật trong giai đoạn đầu tư/xây dựng; tốc độ khai thác là giới hạn tối đa/tối thiểu cho phép phương tiện lưu thông. Nghĩa vụ của người lái là chấp hành quy định tốc độ áp dụng, không dùng giá trị thiết kế công trình làm tốc độ được phép. Căn cứ khoản 1, điểm a khoản 2 Điều 26 của 49/VBHN-VPQH và khoản 1 Điều 12 của 55/VBHN-VPQH. Không kết luận thủ tục đo, biển cụ thể hay chứng cứ xử phạt một vụ việc.

Required facets:

- f1 [definition/positive_support]: Phân biệt vận tốc tính thiết kế với giới hạn khai thác cho phương tiện. (groups: g1)
- f2 [reasoning/positive_support]: Nghĩa vụ chấp hành tốc độ áp dụng cho người lái; không tự dùng tốc độ thiết kế. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d26-k1` — khoản 1 Điều 26 49/VBHN-VPQH; eligible=True; operations=none
- g1/support: `49-vbhn-vpqh-d26-k2-pa` — điểm a khoản 2 Điều 26 49/VBHN-VPQH; eligible=True; operations=none
- g2/support: `55-vbhn-vpqh-d12-k1` — khoản 1 Điều 12 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 27 — edit

- Gốc: Tôi là chủ xe ô tô. Tôi cho bạn tôi mượn xe, biết rõ là bạn tôi chưa có bằng lái xe. Nếu bị phát hiện, tôi (chủ xe) bị phạt như thế nào?
- Query audit: Tôi là cá nhân chủ xe ô tô, biết bạn tôi không có giấy phép lái xe mà vẫn giao xe để bạn lái trên đường. Tôi, với tư cách chủ xe, bị phạt bao nhiêu tiền?
- Lý do: Làm rõ chủ xe cá nhân, giao xe điều khiển trên đường và chỉ hỏi mức tiền; không gộp nhánh chủ xe tổ chức.
- Loại/family: scenario / historical_027
- Tags: money, condition, cross_document
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Chủ xe cá nhân thuộc nhánh giao xe cho người không đủ điều kiện bị phạt 28.000.000–30.000.000 đồng theo điểm i khoản 14 Điều 32 Nghị định 168/2024/NĐ-CP trong snapshot. Nghĩa vụ có GPLX còn điểm/còn hiệu lực phù hợp loại xe nằm tại khoản 1 Điều 56, 55/VBHN-VPQH; không lấy mức phạt tổ chức 56–60 triệu cho cá nhân.

Required facets:

- f1 [condition/positive_support]: Người lái không đủ điều kiện GPLX; đọc đầy đủ clause head Điều 56. (groups: g1)
- f2 [money/positive_support]: 28–30 triệu đồng đúng chủ xe cá nhân. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d56-k1-pb` — điểm b khoản 1 Điều 56 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d32-k14-pi` — điểm i khoản 14 Điều 32 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 28 — edit

- Gốc: Lắp đặt và sử dụng còi, đèn ưu tiên (đèn nháy xanh đỏ) trái phép trên xe ô tô (không phải xe ưu tiên) bị phạt thế nào?
- Query audit: Người lái ô tô không được quyền ưu tiên nhưng lắp đặt, sử dụng còi hoặc đèn phát tín hiệu ưu tiên trái quy định thì bị phạt tiền và xử lý thiết bị như thế nào?
- Lý do: Chuẩn hóa thiết bị phát tín hiệu và yêu cầu hai facet tiền/thiết bị; không coi mọi đèn màu là thiết bị ưu tiên.
- Loại/family: penalty / historical_028
- Tags: money, additional_sanction, multiple_facets, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Đối với đúng thiết bị phát tín hiệu ưu tiên và chủ thể nêu trong câu: phạt 4.000.000–6.000.000 đồng theo điểm e khoản 5 Điều 6; thiết bị phát tín hiệu ưu tiên lắp đặt/sử dụng trái quy định bị tịch thu theo điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [money/positive_support]: 4–6 triệu đồng, đúng xe không có quyền ưu tiên. (groups: g1)
- f2 [additional_sanction/positive_support]: Tịch thu thiết bị, liên kết điểm e khoản 5 với khoản 15. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k5-pe` — điểm e khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k5-pe` — điểm e khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k15-pa` — điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 29 — keep

- Gốc: Đoàn xe tang (xe đám ma) có nằm trong danh sách "xe ưu tiên" không? Nếu có thì xe tang có được phép vượt đèn đỏ như xe cứu thương không?
- Query audit: Đoàn xe tang (xe đám ma) có nằm trong danh sách "xe ưu tiên" không? Nếu có thì xe tang có được phép vượt đèn đỏ như xe cứu thương không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_029
- Tags: exception, negative_conclusion, multi_locator
- Expectation: abstain; coverage=insufficient; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phần có positive support: đoàn xe tang được liệt kê là xe ưu tiên tại khoản 1 và điểm đ khoản 2 Điều 27 của 55/VBHN-VPQH. Khoản 4 mô tả quyền đi không phụ thuộc đèn cho nhóm điểm a, b, c, d. Không được tự mở rộng quyền đó cho đoàn xe tang; policy V2 hiện chưa cho công bố kết luận âm đầy đủ nếu thiếu negative-support provenance. Draft nêu phạm vi đã biết và giới hạn, chưa chốt câu trả lời phủ định toàn bộ.

Required facets:

- f1 [rule/positive_support]: Đoàn xe tang có trong danh sách xe ưu tiên. (groups: g1)
- f2 [exception/unknown]: Đối chiếu phạm vi nhóm a–d trong khoản 4; không coi context là completeness mọi ngoại lệ. (groups: g2)
- f3 [uncertainty/unknown]: Reviewer cần provenance cho kết luận không được vượt đèn đỏ theo policy hiện tại. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d27-k1` — khoản 1 Điều 27 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d27-k2-pđ` — điểm đ khoản 2 Điều 27 55/VBHN-VPQH; eligible=True; operations=none
- g2/context: `55-vbhn-vpqh-d27-k4` — khoản 4 Điều 27 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Duyệt phạm vi danh sách a–d và cơ sở của kết luận âm; không dùng việc không có điểm đ trong một leaf để tự chứng minh đầy đủ.

## Câu 30 — keep

- Gốc: Tôi có bằng lái xe tích hợp A1 và B. Nếu tôi lái xe máy (A1) vi phạm và bị trừ điểm, thì điểm đó có ảnh hưởng đến việc tôi lái xe ô tô (B) không?
- Query audit: Tôi có bằng lái xe tích hợp A1 và B. Nếu tôi lái xe máy (A1) vi phạm và bị trừ điểm, thì điểm đó có ảnh hưởng đến việc tôi lái xe ô tô (B) không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_030
- Tags: condition, direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Điểm d khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP quy định khi GPLX tích hợp phần không thời hạn và phần có thời hạn, vi phạm khi điều khiển xe mô tô được trừ vào phần không thời hạn; vi phạm khi lái ô tô được trừ vào phần có thời hạn. Với dữ kiện lái mô tô A1, việc trừ điểm áp vào phần mô tô không thời hạn. Đây là quy tắc phân định phần bị trừ, không kết luận mọi vấn đề quyền lái khi GPLX bị tước hoặc có vi phạm khác.

Required facets:

- f1 [rule/positive_support]: Chỉ đúng phần GPLX bị trừ theo loại phương tiện đang điều khiển. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d50-k1-pd` — điểm d khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 31 — keep

- Gốc: "Ùn tắc giao thông đường bộ" được định nghĩa như thế nào?
- Query audit: "Ùn tắc giao thông đường bộ" được định nghĩa như thế nào?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / historical_031
- Tags: definition, direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Ùn tắc giao thông đường bộ là tình trạng người, phương tiện tham gia giao thông bị dồn ứ, di chuyển với tốc độ rất chậm hoặc không thể di chuyển được, theo khoản 11 Điều 2, 55/VBHN-VPQH.

Required facets:

- f1 [definition/positive_support]: Đủ yếu tố dồn ứ, tốc độ rất chậm hoặc không thể di chuyển. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d2-k11` — khoản 11 Điều 2 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 32 — edit

- Gốc: Theo Luật Đường bộ 2024, "Đường gom" là gì?
- Query audit: Đường gom là gì?
- Lý do: Bỏ tên luật/năm, giữ câu định nghĩa tự nhiên.
- Loại/family: factual / historical_032
- Tags: definition, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Đường gom gom hệ thống đường giao thông nội bộ của các khu đô thị, công nghiệp, kinh tế, dân cư, thương mại–dịch vụ và các đường khác vào đường chính hoặc đường nhánh trước khi đấu nối vào đường chính; có thể là đường bên theo khoản 4 Điều 9. Căn cứ khoản 3 Điều 9, 49/VBHN-VPQH.

Required facets:

- f1 [definition/positive_support]: Đúng chức năng gom trước đấu nối và khả năng là đường bên. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d9-k3` — khoản 3 Điều 9 49/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 33 — keep

- Gốc: Khi người điều khiển giao thông (Cảnh sát giao thông) giơ tay thẳng đứng, hiệu lệnh này có ý nghĩa gì đối với người tham gia giao thông?
- Query audit: Khi người điều khiển giao thông (Cảnh sát giao thông) giơ tay thẳng đứng, hiệu lệnh này có ý nghĩa gì đối với người tham gia giao thông?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: factual / historical_033
- Tags: direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Tay bên phải giơ thẳng đứng báo hiệu người tham gia giao thông ở tất cả các hướng phải dừng lại, theo điểm a khoản 3 Điều 11 của 55/VBHN-VPQH. Không chỉ người đi từ một hướng.

Required facets:

- f1 [rule/positive_support]: Tất cả hướng phải dừng khi tay phải giơ thẳng đứng. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d11-k3-pa` — điểm a khoản 3 Điều 11 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 34 — edit

- Gốc: Theo Nghị định 168/2024/NĐ-CP, nguyên tắc trừ điểm giấy phép lái xe trong trường hợp một cá nhân thực hiện nhiều hành vi vi phạm trong cùng một lần xử phạt là gì?
- Query audit: Một cá nhân có từ hai hành vi bị trừ điểm giấy phép lái xe trở lên và bị xử phạt trong cùng một lần thì điểm bị trừ được tính thế nào?
- Lý do: Bỏ số hiệu văn bản; nêu điều kiện từ hai hành vi có chế tài trừ điểm và cùng lần để không nhầm cộng điểm qua nhiều lần.
- Loại/family: factual / historical_034
- Tags: condition, reasoning, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Chỉ áp dụng trừ điểm đối với hành vi bị trừ nhiều điểm nhất theo điểm b khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP. Điều kiện là cùng một lần xử phạt và có từ hai hành vi theo quy định bị trừ điểm; không áp dụng nguyên tắc này cho các lần xử phạt tách biệt.

Required facets:

- f1 [rule/positive_support]: Chọn mức trừ lớn nhất, giữ đúng điều kiện cùng lần; không cộng cơ học. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d50-k1-pb` — điểm b khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 35 — edit

- Gốc: "Thanh toán điện tử giao thông đường bộ" là gì theo quy định của Luật Đường bộ?
- Query audit: Thanh toán điện tử giao thông đường bộ là gì?
- Lý do: Bỏ câu dẫn tên luật, giữ nhu cầu định nghĩa.
- Loại/family: factual / historical_035
- Tags: definition, source_cue_removed
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Là thanh toán các loại phí, giá, tiền dịch vụ liên quan đến hoạt động giao thông của phương tiện đường bộ thông qua tài khoản giao thông, theo khoản 1 Điều 43 của 49/VBHN-VPQH.

Required facets:

- f1 [definition/positive_support]: Đủ đối tượng phí/giá/tiền dịch vụ và phương thức qua tài khoản giao thông. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `49-vbhn-vpqh-d43-k1` — khoản 1 Điều 43 49/VBHN-VPQH; eligible=True; operations=none

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

## Câu 37 — keep

- Gốc: Người điều khiển xe mô tô, xe gắn máy không đội "mũ bảo hiểm cho người đi mô tô, xe máy" khi tham gia giao thông bị phạt bao nhiêu tiền?
- Query audit: Người điều khiển xe mô tô, xe gắn máy không đội "mũ bảo hiểm cho người đi mô tô, xe máy" khi tham gia giao thông bị phạt bao nhiêu tiền?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: penalty / historical_037
- Tags: money, direct
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Người điều khiển xe mô tô/xe gắn máy không đội mũ bảo hiểm theo mô tả bị phạt 400.000–600.000 đồng theo điểm h khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP. Căn cứ này cũng nêu đội mũ nhưng không cài quai đúng quy cách; không lẫn chế tài chở người không đội mũ.

Required facets:

- f1 [money/positive_support]: 400.000–600.000 đồng cho người điều khiển không đội mũ. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d7-k2-ph` — điểm h khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 38 — edit

- Gốc: Hành vi điều khiển xe ô tô đi ngược chiều trên đường cao tốc bị xử phạt như thế nào (tiền phạt và điểm giấy phép lái xe)?
- Query audit: Người lái ô tô thông thường, không phải xe ưu tiên đang làm nhiệm vụ khẩn cấp, đi ngược chiều trên đường cao tốc bị phạt tiền và trừ điểm như thế nào?
- Lý do: Loại trừ nhánh xe ưu tiên khẩn cấp, giữ phân biệt đường cao tốc với đường thông thường.
- Loại/family: penalty / expressway_reverse_direction
- Tags: money, license_points, exception, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 30.000.000–40.000.000 đồng theo điểm đ khoản 11 Điều 6 và trừ 10 điểm GPLX theo điểm d khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [money/positive_support]: 30–40 triệu đồng đúng đường cao tốc. (groups: g1)
- f2 [license_points/positive_support]: 10 điểm và giữ ngoại lệ trong locator hành vi. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k11-pđ` — điểm đ khoản 11 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k11-pđ` — điểm đ khoản 11 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k16-pd` — điểm d khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 39 — edit

- Gốc: Người điều khiển xe tải chở hàng vượt trọng tải (khối lượng hàng chuyên chở) cho phép từ trên 30% đến 50% bị phạt bao nhiêu tiền?
- Query audit: Người lái xe tải chở hàng vượt khối lượng hàng chuyên chở cho phép ghi trong chứng nhận kiểm định trên 30% đến 50%, không đồng thời là chủ xe, bị phạt bao nhiêu tiền?
- Lý do: Làm rõ đại lượng quá tải và chủ thể người lái không đồng thời chủ xe; tránh nhầm tải trọng trục/đường hoặc chế tài chủ xe.
- Loại/family: penalty / historical_039
- Tags: money, numeric, boundary, condition
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 3.000.000–5.000.000 đồng theo điểm a khoản 5 Điều 21 Nghị định 168/2024/NĐ-CP. Khoảng mở ở 30% và đóng ở 50%; căn cứ là khối lượng hàng chuyên chở cho phép trong chứng nhận kiểm định.

Required facets:

- f1 [money/positive_support]: 3–5 triệu đồng và đúng đại lượng/đối tượng. (groups: g1)
- f2 [reasoning/positive_support]: Trên 30% đến 50%: không bao gồm đúng 30%, có đúng 50%. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d21-k5-pa` — điểm a khoản 5 Điều 21 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP; eligible=True; operations=a19-p11-nd168-d21-k5-a
- g2/support: `nd168-effective-as-of-2026-09-22-d21-k5-pa` — điểm a khoản 5 Điều 21 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP; eligible=True; operations=a19-p11-nd168-d21-k5-a

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 40 — edit

- Gốc: Lái xe ô tô không nhường đường hoặc gây cản trở xe được quyền ưu tiên đang phát tín hiệu ưu tiên đi làm nhiệm vụ thì bị phạt bao nhiêu tiền?
- Query audit: Người lái ô tô không nhường đường hoặc cản trở xe có quyền ưu tiên đang phát tín hiệu ưu tiên đi làm nhiệm vụ, không gây tai nạn, bị phạt bao nhiêu tiền?
- Lý do: Làm rõ nhánh không gây tai nạn, giữ hai điều kiện tín hiệu và làm nhiệm vụ.
- Loại/family: penalty / historical_040
- Tags: money, condition
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Phạt 6.000.000–8.000.000 đồng theo điểm b khoản 6 Điều 6 Nghị định 168/2024/NĐ-CP đối với hành vi và điều kiện nêu trong câu.

Required facets:

- f1 [money/positive_support]: 6–8 triệu đồng và giữ đúng xe ưu tiên đang phát tín hiệu đi làm nhiệm vụ. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k6-pb` — điểm b khoản 6 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 41 — edit

- Gốc: Hôm qua tôi lái xe ô tô đi làm về lúc 6 rưỡi tối (18h30). Trời mùa hè vẫn còn sáng nên tôi quên không bật đèn xe. Trường hợp này tôi có bị Cảnh sát giao thông phạt không?
- Query audit: Ngày 22/09/2026 lúc 18 giờ 30, tôi lái ô tô trên đường mà không bật đèn chiếu sáng phía trước. Trời vẫn còn sáng và tôi không gây tai nạn. Tôi có vi phạm không, mức phạt tiền là bao nhiêu?
- Lý do: Thay hôm qua/mùa hè bằng ngày cutoff và giờ cố định; thêm nhánh không tai nạn để có mức phạt xác định, không để luật phụ thuộc ngày chạy test.
- Loại/family: scenario / historical_041
- Tags: explicit_date, reasoning, cross_document, money
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: explicit_date; cutoff=2026-09-22; explicit_date=2026-09-22
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

18h30 nằm trong thời gian 18h–06h phải bật đèn chiếu sáng phía trước, không phụ thuộc trời vẫn sáng, theo khoản 1 Điều 20 của 55/VBHN-VPQH. Hành vi của người lái ô tô ở nhánh đã nêu bị phạt 800.000–1.000.000 đồng theo điểm g khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [reasoning/positive_support]: Áp mốc giờ độc lập với cảm nhận còn sáng. (groups: g1)
- f2 [money/positive_support]: 800.000–1.000.000 đồng cho ô tô không sử dụng đèn. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d20-k1` — khoản 1 Điều 20 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k3-pg` — điểm g khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 42 — keep

- Gốc: Xe ô tô của tôi bị nổ lốp trên đường cao tốc. Tôi đã bật đèn khẩn cấp và đặt tam giác cảnh báo cách đuôi xe khoảng 50 mét. Như vậy tôi có làm đúng luật không và có bị phạt không?
- Query audit: Xe ô tô của tôi bị nổ lốp trên đường cao tốc. Tôi đã bật đèn khẩn cấp và đặt tam giác cảnh báo cách đuôi xe khoảng 50 mét. Như vậy tôi có làm đúng luật không và có bị phạt không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_042
- Tags: missing_facts, condition, cross_document
- Expectation: conditional; coverage=conditional; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Cần biết xe đã vào làn dừng khẩn cấp hay còn trên làn xe chạy. Nếu xe không thể vào làn khẩn cấp, khoản 2 Điều 25 của 55/VBHN-VPQH yêu cầu đèn khẩn cấp, cảnh báo phía sau tối thiểu 150 m và nhanh chóng báo cơ quan chức năng; 50 m không đáp ứng nhánh đó. Điểm c khoản 7 Điều 6 Nghị định 168/2024/NĐ-CP có chế tài 12–14 triệu cho nhánh vi phạm mô tả. Không áp mốc 150 m và tiền phạt vô điều kiện khi chưa rõ vị trí và tình huống dừng.

Required facets:

- f1 [condition/positive_support]: Phân biệt làn dừng khẩn cấp với không thể di chuyển vào làn; giữ yêu cầu tối thiểu 150 m của đúng nhánh. (groups: g1)
- f2 [money/positive_support]: Chế tài nhánh dừng cao tốc vi phạm tại điểm c khoản 7 là 12–14 triệu, không chọn nhánh khi chưa rõ facts. (groups: g2)
- f3 [uncertainty/unknown]: Thiếu vị trí xe và các điều kiện quyết định hành vi. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d25-k2` — khoản 2 Điều 25 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k7-pc` — điểm c khoản 7 Điều 6 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP; eligible=True; operations=a19-p04-nd168-d6-k7-c

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

## Câu 44 — edit

- Gốc: Tôi lái xe ô tô đến đón người thân ở cổng Ủy ban nhân dân huyện. Tôi đã dừng xe sát lề đường bên phải, cách cổng trụ sở khoảng 3 mét để người thân lên xe. Tôi có bị vi phạm lỗi dừng đỗ không?
- Query audit: Tôi dừng ô tô sát lề đường bên phải, cách cổng trụ sở một cơ quan 3 m để đón người thân. Tôi chưa rõ cổng này có bố trí đường cho xe ra vào hay không. Có đủ dữ kiện kết luận tôi vi phạm lỗi dừng xe không?
- Lý do: Bỏ tên UBND huyện để tránh phụ thuộc mô hình hành chính cũ; làm rõ điều kiện cổng có đường xe ra/vào đang thiếu, giữ bài vị trí 3 m.
- Loại/family: scenario / historical_044
- Tags: missing_facts, condition, numeric, cross_document
- Expectation: conditional; coverage=conditional; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Chưa đủ dữ kiện. Điểm k khoản 4 Điều 18 của 55/VBHN-VPQH và điểm đ khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP nêu phạm vi cổng trụ sở cơ quan/tổ chức có bố trí đường cho xe ra, vào. Nếu đúng điều kiện đó, khoảng 3 m thuộc phạm vi 5 m, nhánh tiền phạt 800.000–1.000.000 đồng. Cần xác minh điều kiện cổng và không suy sát lề phải là đủ hợp pháp trong mọi trường hợp.

Required facets:

- f1 [condition/positive_support]: Cổng có bố trí đường xe ra/vào là điều kiện phải xác minh; 3<5 m. (groups: g1)
- f2 [money/positive_support]: Nhánh vi phạm tại điểm đ khoản 3: 800.000–1.000.000 đồng. (groups: g2)
- f3 [uncertainty/unknown]: Chưa rõ điều kiện cổng nên chưa kết luận một nhánh. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d18-k4-pk` — điểm k khoản 4 Điều 18 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k3-pđ` — điểm đ khoản 3 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 45 — edit

- Gốc: Tôi đang lái xe ô tô trên đường quốc lộ (ngoài khu đông dân cư), biển báo cho phép chạy tối đa 80km/h. Do vội nên tôi đã chạy lên 92km/h. Với tốc độ này tôi bị phạt ở mức nào?
- Query audit: Tôi lái ô tô thông thường trên quốc lộ, biển báo cho phép tối đa 80 km/h, thực tế chạy 92 km/h và không gây tai nạn. Tôi bị phạt bao nhiêu tiền?
- Lý do: Nêu ô tô thông thường và không tai nạn để cô lập nhánh; giữ phép suy luận 92−80.
- Loại/family: scenario / car_speed_10_20
- Tags: money, numeric, reasoning
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

92−80=12 km/h, thuộc khoảng từ 10 đến 20 km/h. Mức phạt 4.000.000–6.000.000 đồng theo điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP.

Required facets:

- f1 [reasoning/positive_support]: Tính vượt 12 km/h, chọn đúng khoảng 10–20. (groups: g1)
- f2 [money/positive_support]: 4–6 triệu đồng đúng nhánh ô tô. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `nd168-effective-as-of-2026-09-22-d6-k5-pđ` — điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d6-k5-pđ` — điểm đ khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 46 — keep

- Gốc: Xe cứu thương đang trên đường đi đón bệnh nhân cấp cứu (chưa có bệnh nhân trên xe) thì có được phép vượt đèn đỏ không? Tại sao?
- Query audit: Xe cứu thương đang trên đường đi đón bệnh nhân cấp cứu (chưa có bệnh nhân trên xe) thì có được phép vượt đèn đỏ không? Tại sao?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / historical_046
- Tags: missing_facts, condition, exception, multi_locator
- Expectation: conditional; coverage=conditional; allowed=insufficient_evidence
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Việc xe chưa có bệnh nhân không tự quyết định quyền ưu tiên: cần xác định xe đang thực hiện nhiệm vụ cấp cứu và các điều kiện tín hiệu/hiệu lệnh áp dụng. Khoản 1, điểm c khoản 2, điểm a khoản 3 và khoản 4 Điều 27 của 55/VBHN-VPQH quy định xe cứu thương làm nhiệm vụ và phạm vi ưu tiên; vẫn phải tuân hiệu lệnh người điều khiển giao thông/biển tạm thời. Không khẳng định mọi xe đang đi đón bệnh nhân đều được vượt đèn đỏ chỉ từ dữ kiện chưa có bệnh nhân.

Required facets:

- f1 [condition/positive_support]: Nhiệm vụ cấp cứu, tín hiệu và phạm vi quyền ưu tiên của xe cứu thương. (groups: g1)
- f2 [uncertainty/unknown]: Chưa rõ nhiệm vụ/tín hiệu/hiệu lệnh cụ thể; không khẳng định một nhánh. (groups: none)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d27-k1` — khoản 1 Điều 27 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d27-k2-pc` — điểm c khoản 2 Điều 27 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d27-k3-pa` — điểm a khoản 3 Điều 27 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `55-vbhn-vpqh-d27-k4` — khoản 4 Điều 27 55/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

## Câu 47 — edit

- Gốc: Tôi đi xe máy, đeo tai nghe để nghe chỉ dẫn đường từ Google Maps cho tiện. Tôi có bị phạt không? Luật quy định thế nào về việc này?
- Query audit: Tôi lái xe mô tô, đeo tai nghe âm thanh để nghe chỉ dẫn Google Maps, không phải thiết bị trợ thính. Hành vi này có bị cấm và mức phạt tiền là bao nhiêu?
- Lý do: Làm rõ người lái, thiết bị âm thanh và loại trừ trợ thính; hỏi đúng quy tắc/mức tiền thay vì mọi hệ quả.
- Loại/family: scenario / historical_047
- Tags: money, exception, cross_document, multiple_facets
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Người lái mô tô bị cấm sử dụng thiết bị âm thanh, trừ thiết bị trợ thính, theo điểm c khoản 3 Điều 33 của 55/VBHN-VPQH. Hành vi sử dụng thiết bị âm thanh ở nhánh đã nêu bị phạt 800.000–1.000.000 đồng theo điểm đ khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP. Mục đích nghe Maps không thay đổi mô tả thiết bị/hành vi trong căn cứ.

Required facets:

- f1 [rule/positive_support]: Đúng chủ thể người lái và ngoại lệ trợ thính. (groups: g1)
- f2 [money/positive_support]: 800.000–1.000.000 đồng cho sử dụng thiết bị âm thanh. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d33-k3-pc` — điểm c khoản 3 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k4-pđ` — điểm đ khoản 4 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

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

## Câu 49 — edit

- Gốc: Khi tôi đang vượt một xe container dài trên đường quốc lộ, để vượt nhanh và an toàn, tôi có được phép chạy quá tốc độ tối đa cho phép của đoạn đường đó trong thời gian ngắn không?
- Query audit: Khi vượt xe container trên quốc lộ, tôi có phải tiếp tục tuân thủ tốc độ tối đa cho phép của đoạn đường, kể cả chỉ vượt trong thời gian ngắn, không?
- Lý do: Giữ nhu cầu về tốc độ khi vượt nhưng viết thành nghĩa vụ dương có căn cứ; không yêu cầu suy từ thiếu evidence về ngoại lệ.
- Loại/family: scenario / historical_049
- Tags: rule, reasoning
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Có. Người lái phải chấp hành quy định về tốc độ theo khoản 1 Điều 12 của 55/VBHN-VPQH. Tốc độ khai thác là giới hạn cho phép phương tiện tham gia giao thông theo điểm a khoản 2 Điều 26 của 49/VBHN-VPQH. Việc vượt xe và thời gian ngắn không thay thế nghĩa vụ dương đã nêu; câu này không đánh giá một vụ xử phạt có xe ưu tiên hoặc điều kiện đặc biệt.

Required facets:

- f1 [rule/positive_support]: Nghĩa vụ chấp hành tốc độ áp dụng vẫn là yêu cầu cho người lái trong tình huống đã nêu. (groups: g1)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d12-k1` — khoản 1 Điều 12 55/VBHN-VPQH; eligible=True; operations=none
- g1/support: `49-vbhn-vpqh-d26-k2-pa` — điểm a khoản 2 Điều 26 49/VBHN-VPQH; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer kiểm tra cách diễn đạt nghĩa vụ dương, tránh biến nó thành chứng minh không tồn tại mọi ngoại lệ; nếu cần nới phạm vi query, phải đổi expectation.

## Câu 50 — keep

- Gốc: Nhà tôi có 4 người (2 vợ chồng và 2 con nhỏ, một bé 3 tuổi, một bé 5 tuổi). Chúng tôi có được phép đi chung trên một chiếc xe máy (xe mô tô 2 bánh) không?
- Query audit: Nhà tôi có 4 người (2 vợ chồng và 2 con nhỏ, một bé 3 tuổi, một bé 5 tuổi). Chúng tôi có được phép đi chung trên một chiếc xe máy (xe mô tô 2 bánh) không?
- Lý do: Giữ nhu cầu gốc; audit lại căn cứ và đáp án tại cutoff, không sử dụng gold cũ.
- Loại/family: scenario / motorcycle_passengers
- Tags: numeric, exception, multi_locator
- Expectation: publish; coverage=sufficient; allowed=answered
- Temporal: frozen_corpus; cutoff=2026-09-22; explicit_date=None
- Review: needs_review; drafted=2026-10-09; author=Codex — technical draft; independent legal review pending

Đáp án tham chiếu **draft**:

Một người lái chở thêm vợ/chồng và hai con là chở 03 người, tổng 04 người trên mô tô. Khoản 1 Điều 33 của 55/VBHN-VPQH chỉ cho tối đa hai người được chở trong ngoại lệ trẻ em dưới 12 tuổi; không nâng tối đa lên ba người được chở. Hành vi chở từ 03 người trở lên có quy định xử phạt tại điểm b khoản 3 Điều 7 Nghị định 168/2024/NĐ-CP. Vì vậy dữ kiện không đáp ứng giới hạn chở người; không suy miễn phạt vì cả hai trẻ nhỏ.

Required facets:

- f1 [reasoning/positive_support]: Đếm 03 người được chở, không nhầm tổng số người gồm người lái. (groups: g1)
- f2 [exception/positive_support]: Ngoại lệ dưới 12 tuổi vẫn tối đa hai người được chở; có quy định chở từ 03 trở lên. (groups: g2)

Evidence (nội dung/context đầy đủ ở evidence_catalog.json):

- g1/support: `55-vbhn-vpqh-d33-k1-pc` — điểm c khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `55-vbhn-vpqh-d33-k1-pc` — điểm c khoản 1 Điều 33 55/VBHN-VPQH; eligible=True; operations=none
- g2/support: `nd168-effective-as-of-2026-09-22-d7-k3-pb` — điểm b khoản 3 Điều 7 Nghị định 168/2024/NĐ-CP; eligible=True; operations=none

Điểm reviewer cần chốt:

- Reviewer độc lập đối chiếu từng facet với source spans và full context trước khi approved.

