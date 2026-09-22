# Tiến độ Milestone 5

**Cập nhật:** 22/09/2026

## Đang ở đâu?

Pha Legal Corpus Refresh đã đạt **gate nguồn kỹ thuật**.

- Nguồn 238: đã xác minh chính thức.
- Amendment map: 102 operation tại 24 Điều.
- Locator/anchor: 102/102 đạt.
- Lỗi `điểm d`/`điểm đ`: đã sửa và có test regression.
- Effective view: đã dựng 1.308 locator, áp dụng và đối chiếu 102/102 operation.
- Tại cutoff: 1.302 locator active; 3 locator mixed mốc 2028 bị chặn publication;
  3 locator chưa hiệu lực tới năm 2029.
- Đã sửa lỗi mô hình thời gian từng đánh dấu cả 3 locator mốc 2028 là future.
- Policy fail-closed cho 3 locator mixed mốc 2028: chủ dự án đã duyệt.
- Legal review effective view: đã đạt; được phép chuẩn bị snapshot/shadow index.
- Citation/provenance và source line: đạt 102/102.
- 49/VBHN-VPQH: DOCX Công báo tái tạo đúng text, đủ 86 Điều và 41 footnote.
- 55/VBHN-VPQH: DOCX Công báo tái tạo đúng text, đủ 89 Điều và 47 footnote.
- Text 168 do chủ dự án cung cấp: khớp 55/55 Điều với hai PDF Công báo.
- Hai bản `extracted-layout.txt` lỗi của 49/55: đã xóa để tránh dùng nhầm.
- Production index: chưa thay đổi.
- Freeze corpus: đủ điều kiện nguồn, nhưng chưa freeze vì chưa build/kiểm tra shadow index.

## Còn chặn Pha 1

1. Chưa tạo processed corpus cuối cùng.
2. Chưa build/kiểm tra shadow Weaviate/BM25 và freeze snapshot mới.

## Benchmark

50 câu cũ chỉ còn là nguồn câu hỏi. Answer, citation và gold sẽ được làm lại sau
khi current-law snapshot ổn định. Không so sánh V1 với V2.

## File nên xem

1. `docs/MILESTONE_5_STATUS.md` — tiến độ ngắn gọn này.
2. `docs/MILESTONE_5.md` — roadmap và gate.
3. `data/legal_sources/nd168_effective_view_review.json` — kết quả review và
   policy đã được duyệt.
4. `data/legal_sources/source_extraction_review.json` — audit nguồn 49/55/168.

## Bước tiếp theo

Tạo processed corpus và shadow Weaviate/BM25; chưa thay production index.
