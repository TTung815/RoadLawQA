# Development reviewed v1

54 đơn vị đã owner duyệt theo 7 mục A1–A4, B1–B2, C1 trong hội thoại ngày
11/10/2026; ghi nhận/freeze 12/10/2026. Owner internal content/scope review,
không phải review luật sư hoặc xác nhận production.

Draft/design/50 gold/corpus vẫn nguyên; wrapper `parent_case` giữ draft needs_review
để bảo toàn provenance, `gold` cấp ngoài là gold approved dùng evaluation.
Approval-only version, không sửa query/answer/evidence/rationale gốc. Các ghi chú
author “chưa review” trong parent mô tả trạng thái trước owner approval.

Modes: 12 end-to-end, 7 fixed-evidence, 1 rewrite, 34 guards. Không gộp mẫu số,
không gọi 54 units là 54 câu luật độc lập. Exposure legacy/regression không đổi.
Guard blocked chỉ context, gold abstain; owner review không gỡ publication blocks.

```bash
.venv/bin/python -m evaluation.reviewed_development_dataset verify
```

[REVIEWED.md](REVIEWED.md) là nội dung, owner_review.json là quyết định theo nhóm,
manifest/freeze_receipt.json khóa artifact và binding parent. Thay đổi cần version
mới. Hướng dẫn chạy/chấm: [EVALUATION_QUICKSTART.md](../../../docs/EVALUATION_QUICKSTART.md).
Freeze không chứng minh mô hình trả lời đúng; chưa chạy C0–C4 ở checkpoint này.
