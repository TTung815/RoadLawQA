# Development regression/challenge — draft cần review

16 bài dẫn xuất từ gold đã freeze; **0 bài mới approved**. Chưa chạy model.
Không phải held-out; các biến thể giữ family exposed của parent.
Replay thiếu evidence không đổi full-corpus gold thành abstain.

## dev_001 — Thiếu căn cứ điểm nhưng có mức tiền

Parent: `current_law_005`; family: `historical_005`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Người lái ô tô dùng tay cầm và sử dụng điện thoại khi xe đang di chuyển trên đường, không gây tai nạn, bị phạt bao nhiêu tiền và trừ bao nhiêu điểm giấy phép lái xe?

**Đáp án tham chiếu toàn corpus — draft:**

Với hành vi và điều kiện đã nêu: phạt 4.000.000–6.000.000 đồng (điểm h khoản 5 Điều 6) và trừ 04 điểm GPLX (điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP).

- Full-corpus expectation: publish
- Bài thử: Pool chưa đủ mọi yêu cầu; không công bố câu trả lời đầy đủ như đã grounded.
- Expectation pool được đưa: insufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d6-k5-ph`
- Ý chưa đủ căn cứ trong tổng các batch: Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển.
- Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-ph`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:294–294
- điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k16-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:378–378

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_002 — Control: đủ căn cứ tiền và điểm

Parent: `current_law_005`; family: `historical_005`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Người lái ô tô dùng tay cầm và sử dụng điện thoại khi xe đang di chuyển trên đường, không gây tai nạn, bị phạt bao nhiêu tiền và trừ bao nhiêu điểm giấy phép lái xe?

**Đáp án tham chiếu toàn corpus — draft:**

Với hành vi và điều kiện đã nêu: phạt 4.000.000–6.000.000 đồng (điểm h khoản 5 Điều 6) và trừ 04 điểm GPLX (điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP).

- Full-corpus expectation: publish
- Bài thử: Control pool đủ positive support; đo false-insufficient/unnecessary abstention.
- Expectation pool được đưa: sufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d6-k5-ph`, `nd168-effective-as-of-2026-09-22-d6-k16-pb`
- Ý chưa đủ căn cứ trong tổng các batch: không có

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển.
- Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-ph`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:294–294
- điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k16-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:378–378

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_003 — Thiếu căn cứ chế tài bổ sung

Parent: `current_law_028`; family: `historical_028`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Người lái ô tô không được quyền ưu tiên nhưng lắp đặt, sử dụng còi hoặc đèn phát tín hiệu ưu tiên trái quy định thì bị phạt tiền và xử lý thiết bị như thế nào?

**Đáp án tham chiếu toàn corpus — draft:**

Đối với đúng thiết bị phát tín hiệu ưu tiên và chủ thể nêu trong câu: phạt 4.000.000–6.000.000 đồng theo điểm e khoản 5 Điều 6; thiết bị phát tín hiệu ưu tiên lắp đặt/sử dụng trái quy định bị tịch thu theo điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP.

- Full-corpus expectation: publish
- Bài thử: Pool chưa đủ mọi yêu cầu; không công bố câu trả lời đầy đủ như đã grounded.
- Expectation pool được đưa: insufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d6-k5-pe`
- Ý chưa đủ căn cứ trong tổng các batch: Tịch thu thiết bị, liên kết điểm e khoản 5 với khoản 15.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- 4–6 triệu đồng, đúng xe không có quyền ưu tiên.
- Tịch thu thiết bị, liên kết điểm e khoản 5 với khoản 15.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm e khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-pe`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:290–290
- điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k15-pa`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:368–368

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_004 — Control: đủ tiền và xử lý thiết bị

Parent: `current_law_028`; family: `historical_028`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Người lái ô tô không được quyền ưu tiên nhưng lắp đặt, sử dụng còi hoặc đèn phát tín hiệu ưu tiên trái quy định thì bị phạt tiền và xử lý thiết bị như thế nào?

**Đáp án tham chiếu toàn corpus — draft:**

Đối với đúng thiết bị phát tín hiệu ưu tiên và chủ thể nêu trong câu: phạt 4.000.000–6.000.000 đồng theo điểm e khoản 5 Điều 6; thiết bị phát tín hiệu ưu tiên lắp đặt/sử dụng trái quy định bị tịch thu theo điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP.

- Full-corpus expectation: publish
- Bài thử: Control pool đủ positive support; đo false-insufficient/unnecessary abstention.
- Expectation pool được đưa: sufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d6-k5-pe`, `nd168-effective-as-of-2026-09-22-d6-k15-pa`
- Ý chưa đủ căn cứ trong tổng các batch: không có

Ý bắt buộc (căn cứ không thay đổi từ parent):

- 4–6 triệu đồng, đúng xe không có quyền ưu tiên.
- Tịch thu thiết bị, liên kết điểm e khoản 5 với khoản 15.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm e khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-pe`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:290–290
- điểm a khoản 15 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k15-pa`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:368–368

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_005 — Citation tồn tại nhưng source không hỗ trợ kết luận

Parent: `current_law_005`; family: `historical_005`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Người lái ô tô dùng tay cầm và sử dụng điện thoại khi xe đang di chuyển trên đường, không gây tai nạn, bị phạt bao nhiêu tiền và trừ bao nhiêu điểm giấy phép lái xe?

**Đáp án tham chiếu toàn corpus — draft:**

Với hành vi và điều kiện đã nêu: phạt 4.000.000–6.000.000 đồng (điểm h khoản 5 Điều 6) và trừ 04 điểm GPLX (điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP).

- Full-corpus expectation: publish
- Bài thử: Locator hợp lệ của lỗi khác không chứng minh claim tiền/điểm bài này.
- Expectation pool được đưa: insufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d6-k3-pk`
- Ý chưa đủ căn cứ trong tổng các batch: Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển.; Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển.
- Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-ph`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:294–294
- điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k16-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:378–378

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_006 — Không đổi hành vi thiếu trang bị thành không sử dụng đèn

Parent: `current_law_024`; family: `historical_024`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Một người điều khiển xe đạp tham gia giao thông trên đường. Xe thuộc loại phải có đèn chiếu sáng hoặc tấm phản quang phía trước, nhưng không có cả đèn lẫn tấm phản quang phía trước. Người điều khiển bị phạt bao nhiêu tiền?

**Đáp án tham chiếu toàn corpus — draft:**

Với loại xe và tình trạng thiếu trang bị đã nêu, người điều khiển bị phạt từ 100.000 đến 200.000 đồng theo khoản 1 Điều 15 Nghị định 168/2024/NĐ-CP.

- Full-corpus expectation: publish
- Bài thử: Điều 9 về sử dụng đèn không thay căn cứ thiếu trang bị tại Điều 15.
- Expectation pool được đưa: insufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d9-k1-pi`
- Ý chưa đủ căn cứ trong tổng các batch: Xe thuộc loại phải có đèn chiếu sáng hoặc tấm phản quang phía trước nhưng thiếu cả hai phương án trang bị.; Người điều khiển bị phạt 100.000–200.000 đồng theo khoản 1 Điều 15, không nhầm hành vi không sử dụng đèn/báo hiệu ban đêm ở Điều 9.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Xe thuộc loại phải có đèn chiếu sáng hoặc tấm phản quang phía trước nhưng thiếu cả hai phương án trang bị.
- Người điều khiển bị phạt 100.000–200.000 đồng theo khoản 1 Điều 15, không nhầm hành vi không sử dụng đèn/báo hiệu ban đêm ở Điều 9.

Căn cứ đầy đủ trong evidence_catalog.json:

- khoản 1 Điều 15 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d15-k1`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:1010–1010

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_007 — Giữ căn cứ tiền của batch trước khi batch sau có điểm

Parent: `current_law_008`; family: `historical_008`; mode: `fixed_evidence`.

**Câu hỏi hiện tại:** Một người lái xe mô tô vượt đèn đỏ trên đường, không có hiệu lệnh khác cho phép đi và không gây tai nạn. Người đó bị phạt tiền và trừ điểm giấy phép lái xe như thế nào?

**Đáp án tham chiếu toàn corpus — draft:**

Không chấp hành hiệu lệnh đèn tín hiệu giao thông ở nhánh đã nêu: phạt 4.000.000–6.000.000 đồng theo điểm c khoản 7 Điều 7 và trừ 04 điểm GPLX theo điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP.

- Full-corpus expectation: publish
- Bài thử: Grade ordered union, không chỉ batch cuối; hai facet đều còn evidence.
- Expectation pool được đưa: sufficient; không dùng nhãn này thay full-corpus gold.
- Batch 1: `nd168-effective-as-of-2026-09-22-d7-k7-pc`
- Batch 2: `nd168-effective-as-of-2026-09-22-d7-k13-pb`
- Ý chưa đủ căn cứ trong tổng các batch: không có

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Đúng nhánh xe mô tô: 4–6 triệu đồng.
- 04 điểm, không nhầm điểm của ô tô hoặc nhánh tai nạn.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm c khoản 7 Điều 7 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d7-k7-pc`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:490–490
- điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d7-k13-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:550–550

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_008 — Rewrite giữ tài xế không phải chủ xe và biên khối lượng

Parent: `current_law_039`; family: `historical_039`; mode: `rewrite_probe`.

**Câu hỏi hiện tại:** Tôi là tài xế thuê, không phải chủ xe. Tôi lái xe tải chở hàng vượt khối lượng hàng chuyên chở cho phép ghi trong chứng nhận kiểm định trên 30% đến 50%. Tôi bị phạt bao nhiêu tiền?

**Đáp án tham chiếu toàn corpus — draft:**

Với dữ kiện tài xế không phải chủ xe, mức phạt là 3.000.000–5.000.000 đồng theo điểm a khoản 5 Điều 21 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP. Khoảng trên 30% đến 50% không bao gồm đúng 30% nhưng bao gồm đúng 50%, tính theo khối lượng hàng chuyên chở cho phép ghi trong chứng nhận kiểm định.

- Full-corpus expectation: publish
- Bài thử: Bảo toàn nguyên chủ thể, hành vi, khoảng số và ngày của parent; chưa có rewrite output.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- 3–5 triệu đồng và đúng đại lượng/đối tượng.
- Trên 30% đến 50%: không bao gồm đúng 30%, có đúng 50%.
- Phân biệt tài xế không phải chủ xe với chủ phương tiện trực tiếp điều khiển: nhánh chủ phương tiện được dẫn sang Điều 32.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm a khoản 5 Điều 21 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d21-k5-pa`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:1270–1270; data/raw/legal/238-2026-nd-cp/supporting-text.txt:203–203
- điểm o khoản 3 Điều 47 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d47-k3-po`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:2396–2396

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_009 — Theo dõi chủ thể/hành vi và yêu cầu tiền + điểm qua history

Parent: `current_law_005`; family: `historical_005`; mode: `end_to_end`.

History (dữ kiện người dùng, không bịa câu trả lời assistant):

- user: Người lái ô tô dùng tay cầm và sử dụng điện thoại khi xe đang di chuyển trên đường, không gây tai nạn, bị phạt bao nhiêu tiền và trừ bao nhiêu điểm giấy phép lái xe?

**Câu hỏi hiện tại:** Vậy tiền phạt và số điểm bị trừ là bao nhiêu?

**Đáp án tham chiếu toàn corpus — draft:**

Với hành vi và điều kiện đã nêu: phạt 4.000.000–6.000.000 đồng (điểm h khoản 5 Điều 6) và trừ 04 điểm GPLX (điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP).

- Full-corpus expectation: publish
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phạt 4–6 triệu đồng cho hành vi dùng tay cầm và sử dụng điện thoại khi xe di chuyển.
- Trừ 04 điểm; đối chiếu liên kết điểm h khoản 5 với điểm b khoản 16.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm h khoản 5 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k5-ph`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:294–294
- điểm b khoản 16 Điều 6 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k16-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:378–378

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_010 — Không lấy dữ kiện ô tô từ history cũ cho câu xe mô tô mới

Parent: `current_law_008`; family: `historical_008`; mode: `end_to_end`.

History (dữ kiện người dùng, không bịa câu trả lời assistant):

- user: Người điều khiển xe ô tô không thắt dây đai an toàn khi xe đang chạy trên đường bị phạt bao nhiêu tiền?
- user: Một người lái xe mô tô vượt đèn đỏ trên đường, không có hiệu lệnh khác cho phép đi và không gây tai nạn. Người đó bị phạt tiền và trừ điểm giấy phép lái xe như thế nào?

**Câu hỏi hiện tại:** Vậy trường hợp vừa nói bị xử lý thế nào?

**Đáp án tham chiếu toàn corpus — draft:**

Không chấp hành hiệu lệnh đèn tín hiệu giao thông ở nhánh đã nêu: phạt 4.000.000–6.000.000 đồng theo điểm c khoản 7 Điều 7 và trừ 04 điểm GPLX theo điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP.

- Full-corpus expectation: publish
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Đúng nhánh xe mô tô: 4–6 triệu đồng.
- 04 điểm, không nhầm điểm của ô tô hoặc nhánh tai nạn.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm c khoản 7 Điều 7 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d7-k7-pc`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:490–490
- điểm b khoản 13 Điều 7 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d7-k13-pb`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:550–550

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_011 — Thiếu dữ kiện về ngoại lệ: không chọn nhánh chắc chắn

Parent: `current_law_016`; family: `motorcycle_passengers`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Người lái xe mô tô hai bánh chở theo 2 người trên xe thì có bị phạt không?

**Đáp án tham chiếu toàn corpus — draft:**

Cần biết hai người được chở thuộc trường hợp nào. Quy tắc là chỉ chở một người, nhưng được chở tối đa hai người trong các trường hợp người bệnh đi cấp cứu, áp giải người vi phạm, trẻ em dưới 12 tuổi, người già yếu/người khuyết tật. Nhánh chở hai người không thuộc ngoại lệ có mức phạt 400.000–600.000 đồng. Không chốt người trong câu bị phạt khi chưa biết ngoại lệ.

- Full-corpus expectation: conditional
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Quy tắc chở một người và tối đa hai người ở ngoại lệ, đọc cả clause head.
- Nhánh không ngoại lệ: 400.000–600.000 đồng.
- Chưa biết tuổi/tình trạng/lý do chở hai người; không gán một nhánh.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm a khoản 1 Điều 33 55/VBHN-VPQH (support); `55-vbhn-vpqh-d33-k1-pa`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:335–335
- điểm b khoản 1 Điều 33 55/VBHN-VPQH (support); `55-vbhn-vpqh-d33-k1-pb`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:336–336
- điểm c khoản 1 Điều 33 55/VBHN-VPQH (support); `55-vbhn-vpqh-d33-k1-pc`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:337–337
- điểm d khoản 1 Điều 33 55/VBHN-VPQH (support); `55-vbhn-vpqh-d33-k1-pd`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:338–338
- điểm g khoản 2 Điều 7 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d7-k2-pg`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:422–422

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_012 — Thiếu dependency tuổi chịu xử phạt: không đoán mức phạt

Parent: `current_law_043`; family: `historical_043`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Con trai tôi năm nay 13 tuổi, cháu lấy trộm chìa khóa xe máy (xe ga 110cc) của gia đình để chạy đi chơi và bị công an giữ lại. Xin hỏi ở độ tuổi này cháu bị phạt tiền bao nhiêu?

**Đáp án tham chiếu toàn corpus — draft:**

Nguồn hiện có chưa đủ để xác định mức phạt tiền của người 13 tuổi trong tình huống này. Tuổi được điều khiển xe và tuổi chịu xử phạt hành chính là hai vấn đề khác nhau. Cần đối chiếu Luật Xử lý vi phạm hành chính về đối tượng chịu xử phạt, hiện chưa có trong bộ nguồn đã kiểm chứng của hệ thống.

- Full-corpus expectation: abstain
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Nhận diện thiếu dependency về tuổi chịu xử phạt; không công bố con số/không phạt.

Căn cứ đầy đủ trong evidence_catalog.json:


Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_013 — Thiếu negative-support provenance không được kết luận âm

Parent: `current_law_010`; family: `license_point_recovery`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Tôi bị Cảnh sát giao thông lập biên bản xử phạt và thông báo bị trừ 2 điểm giấy phép lái xe. Tôi đã ra kho bạc nộp phạt xong xuôi vào ngày hôm sau. Vậy 2 điểm bị trừ đó có được cộng lại (hoàn trả) ngay lập tức sau khi tôi đóng tiền không?

**Đáp án tham chiếu toàn corpus — draft:**

Chưa đủ căn cứ đã kiểm chứng trong phạm vi hệ thống để kết luận toàn bộ tình huống. Phần có căn cứ: trừ điểm gắn với hiệu lực quyết định xử phạt; phục hồi đủ 12 điểm cần GPLX chưa bị trừ hết điểm và 12 tháng không bị trừ điểm kể từ lần gần nhất. Cần phân biệt nộp tiền phạt với điều kiện phục hồi điểm; chưa có căn cứ để hứa điểm được cộng lại ngay sau khi nộp tiền.

- Full-corpus expectation: abstain
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phân biệt cơ chế trừ/khôi phục điểm và thời điểm quyết định có hiệu lực.
- Kết luận phủ định hoàn trả ngay cần reviewer xác nhận provenance theo policy negative-support.

Căn cứ đầy đủ trong evidence_catalog.json:

- điểm a khoản 1 Điều 50 Nghị định 168/2024/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d50-k1-pa`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:2530–2530
- khoản 2 Điều 58 55/VBHN-VPQH (support); `55-vbhn-vpqh-d58-k2`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:685–686

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_014 — Đủ rule đã sửa đổi và dữ kiện: đo từ chối không cần thiết

Parent: `current_law_007`; family: `historical_007`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Tôi lái ô tô gia đình 5 chỗ, không kinh doanh vận tải, chở con 9 tuổi cao 1,30 m. Tôi có được cho con ngồi cùng hàng ghế với người lái không và phải dùng thiết bị an toàn nào?

**Đáp án tham chiếu toàn corpus — draft:**

Theo khoản 3 Điều 10 của 55/VBHN-VPQH tại cutoff, trẻ vừa dưới 10 tuổi vừa cao dưới 1,35 m không được ngồi cùng hàng ghế với người lái, trừ ô tô chỉ có một hàng ghế. Xe gia đình 5 chỗ trong câu không thuộc ngoại lệ một hàng ghế; người lái phải sử dụng, hướng dẫn sử dụng thiết bị an toàn phù hợp cho trẻ. Ngoại lệ xe kinh doanh vận tải hành khách đối với thiết bị không áp dụng dữ kiện đã nêu.

- Full-corpus expectation: publish
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Hai điều kiện tuổi và chiều cao đồng thời: 9<10 và 1,30<1,35.
- Không xếp trẻ ngồi cùng hàng ghế người lái; có ngoại lệ xe chỉ một hàng ghế.
- Nghĩa vụ thiết bị phù hợp và ngoại lệ xe kinh doanh vận tải hành khách, không áp dụng xe gia đình.

Căn cứ đầy đủ trong evidence_catalog.json:

- khoản 3 Điều 10 55/VBHN-VPQH (support); `55-vbhn-vpqh-d10-k3`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:114–114

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_015 — Ngày lịch sử có scoped continuity proof; không tự mở lịch sử khác

Parent: `current_law_009`; family: `license_point_recovery`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Giấy phép lái xe của tôi có 12 điểm. Ngày 01/02/2025 tôi bị trừ 2 điểm. Nếu sau đó tôi không vi phạm gì thêm, khi nào giấy phép lái xe của tôi được phục hồi đủ 12 điểm?

**Đáp án tham chiếu toàn corpus — draft:**

Nếu ngày 01/02/2025 là lần bị trừ điểm gần nhất và sau đó bạn không bị trừ thêm điểm, GPLX còn 10 điểm của bạn đủ điều kiện phục hồi đủ 12 điểm khi đủ 12 tháng, tức mốc 01/02/2026. Căn cứ khoản 2 Điều 58, 55/VBHN-VPQH; quy tắc này đã có trong Luật 36/2024/QH15 áp dụng từ 01/01/2025.

- Full-corpus expectation: publish
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- GPLX còn điểm được phục hồi đủ 12 điểm khi không bị trừ điểm trong 12 tháng kể từ lần trừ gần nhất.
- Lần trừ gần nhất 01/02/2025, không bị trừ thêm: mốc đủ 12 tháng là 01/02/2026; không hứa trạng thái dữ liệu thực tế đã cập nhật.

Căn cứ đầy đủ trong evidence_catalog.json:

- khoản 2 Điều 58 55/VBHN-VPQH (support); `55-vbhn-vpqh-d58-k2`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:685–686

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

## dev_016 — Giữ điều kiện thiếu và provenance overlay 238

Parent: `current_law_042`; family: `historical_042`; mode: `end_to_end`.

**Câu hỏi hiện tại:** Xe ô tô của tôi bị nổ lốp trên đường cao tốc. Tôi đã bật đèn khẩn cấp và đặt tam giác cảnh báo cách đuôi xe khoảng 50 mét. Như vậy tôi có làm đúng luật không và có bị phạt không?

**Đáp án tham chiếu toàn corpus — draft:**

Cần biết xe dừng ở làn/dải dừng khẩn cấp hay còn trên phần làn xe chạy. Khoản 2 Điều 25, 55/VBHN-VPQH yêu cầu đèn khẩn cấp và cảnh báo phía sau tối thiểu 150 m khi xe không thể di chuyển vào làn dừng khẩn cấp, cùng việc nhanh chóng báo cơ quan có trách nhiệm. Nếu thuộc nhánh này thì đặt cảnh báo 50 m chưa đáp ứng khoảng cách. Điểm c khoản 7 Điều 6 Nghị định 168/2024/NĐ-CP, được sửa đổi bởi khoản 4 Điều 19 Nghị định 238/2026/NĐ-CP, quy định khung phạt 12–14 triệu đồng cho hành vi vi phạm mô tả, bao gồm phạm vi làn hoặc dải dừng xe khẩn cấp. Chưa đủ dữ kiện để kết luận bạn bị phạt hoặc áp khoảng cách 150 m cho mọi vị trí dừng.

- Full-corpus expectation: conditional
- Bài thử: Đối chiếu full-corpus gold; không suy hệ thống đã đạt từ nhãn dataset.

Ý bắt buộc (căn cứ không thay đổi từ parent):

- Phân biệt làn dừng khẩn cấp với không thể di chuyển vào làn; giữ yêu cầu tối thiểu 150 m của đúng nhánh.
- Chế tài nhánh dừng cao tốc vi phạm tại điểm c khoản 7 là 12–14 triệu, không chọn nhánh khi chưa rõ facts.
- Thiếu vị trí xe và các điều kiện quyết định hành vi.

Căn cứ đầy đủ trong evidence_catalog.json:

- khoản 2 Điều 25 55/VBHN-VPQH (support); `55-vbhn-vpqh-d25-k2`; data/raw/legal/55-vbhn-vpqh/supporting-text.txt:275–275
- điểm c khoản 7 Điều 6 Nghị định 168/2024/NĐ-CP được sửa đổi, bổ sung bởi Nghị định 238/2026/NĐ-CP (support); `nd168-effective-as-of-2026-09-22-d6-k7-pc`; data/raw/legal/168-2024-nd-cp/supporting-text.txt:328–328; data/raw/legal/238-2026-nd-cp/supporting-text.txt:196–196

Reviewer cần chốt:

- Duyệt query/history, ý bắt buộc và full context; approval parent không tự chuyển sang bài này.
- Chốt stage expectation và rubric, phân biệt pool bị cắt với corpus thiếu nguồn.
- Nếu có ngày lịch sử, duyệt scope proof cho chính bài dẫn xuất trước freeze.

