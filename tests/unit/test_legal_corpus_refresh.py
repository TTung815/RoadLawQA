"""Kiểm tra offline cho registry và audit corpus hiện hành."""

from zipfile import ZipFile

from ingestion.corpus_refresh import build_reports, select_document_headings
from ingestion.docx_text import extract_document_text, extract_footnote_audit
from ingestion.legal_registry import (
    DEFAULT_REGISTRY,
    PROJECT_ROOT,
    Registry,
    audit_registry,
    file_digest,
    read_json,
)
from ingestion.source_review import normalize_legal_text


def test_docx_extraction_accepts_backslash_archive_names(tmp_path):
    document = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>Điều 1.</w:t><w:tab/><w:t>Nội dung</w:t></w:r></w:p>
        <w:p><w:r><w:t xml:space="preserve">Khoản 1 </w:t><w:t>tiếp theo</w:t></w:r></w:p>
      </w:body>
    </w:document>""".encode("utf-8")
    source = tmp_path / "source.docx"
    with ZipFile(source, "w") as archive:
        archive.writestr("word\\document.xml", document)
    assert extract_document_text(source) == "Điều 1.\tNội dung\nKhoản 1 tiếp theo\n"


def test_docx_footnotes_are_audited_without_polluting_body_text(tmp_path):
    document = """<?xml version="1.0" encoding="UTF-8"?>
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body><w:p><w:r><w:t>Khoản đã sửa</w:t><w:footnoteReference w:id="2"/></w:r></w:p></w:body>
    </w:document>""".encode("utf-8")
    footnotes = """<?xml version="1.0" encoding="UTF-8"?>
    <w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:footnote w:id="-1"><w:p><w:r><w:t>Dấu phân cách</w:t></w:r></w:p></w:footnote>
      <w:footnote w:id="2"><w:p><w:r><w:t>Sửa bởi Luật mới.</w:t></w:r></w:p></w:footnote>
    </w:footnotes>""".encode("utf-8")
    source = tmp_path / "source.docx"
    with ZipFile(source, "w") as archive:
        archive.writestr("word\\document.xml", document)
        archive.writestr("word\\footnotes.xml", footnotes)

    assert extract_document_text(source) == "Khoản đã sửa\n"
    audit = extract_footnote_audit(source)
    assert audit["footnote_count"] == 1
    assert audit["reference_count"] == 1
    assert audit["unresolved_reference_ids"] == []
    assert audit["notes"] == [
        {
            "footnote_id": 2,
            "text": "Sửa bởi Luật mới.",
            "reference_contexts": ["Khoản đã sửa"],
        }
    ]


def test_heading_selector_ignores_embedded_replacement_articles():
    headings = [
        {"article": 1, "title": "Sửa Điều 3"},
        {"article": 2, "title": "Sửa Điều 6"},
        {"article": 42, "title": "Nội dung Điều 42 được trích"},
        {"article": 3, "title": "Sửa Điều 13"},
    ]
    selected, ignored = select_document_headings(headings, 3)
    assert [row["article"] for row in selected] == [1, 2, 3]
    assert ignored == [{"article": 42, "title": "Nội dung Điều 42 được trích"}]


def test_real_source_registry_is_eligible_for_snapshot_freeze_after_review():
    report = audit_registry()
    assert report["artifact_integrity_passed"]
    assert report["freeze_eligible"]
    assert report["scope_review_status"] == "approved"
    assert report["pending_documents"] == []
    assert not report["blocking_amendment_operations"]


def test_owner_text_and_official_docx_provenance_are_explicit():
    registry = Registry.model_validate(read_json(DEFAULT_REGISTRY))
    documents = {document.document_id: document for document in registry.documents}
    nd168 = documents["168-2024-nd-cp"]
    nd238 = documents["238-2026-nd-cp"]
    law49 = documents["49-vbhn-vpqh"]
    law55 = documents["55-vbhn-vpqh"]
    assert nd168.extraction.path == "data/raw/legal/168-2024-nd-cp/supporting-text.txt"
    assert nd168.extraction.quality == "legacy_text_verified_against_pdf"
    assert nd168.extraction.review.status == "approved"
    assert law49.extraction.quality == "official_docx_text"
    assert law55.extraction.quality == "official_docx_text"
    assert nd238.extraction.quality == "official_docx_text"
    assert nd238.extraction.supporting_input_url.startswith("https://congbao.chinhphu.vn/")
    assert nd238.extraction.review.status == "approved"


def test_source_extraction_review_is_pinned_to_current_artifacts():
    review = read_json(PROJECT_ROOT / "data/legal_sources/source_extraction_review.json")
    assert review["status"] == "passed"
    assert not review["production_index_touched"]
    assert not review["legal_interpretation_reviewed"]
    documents = {row["document_id"]: row for row in review["documents"]}
    assert documents["49-vbhn-vpqh"]["extracted_text"]["article_count"] == 86
    assert documents["55-vbhn-vpqh"]["extracted_text"]["article_count"] == 89
    assert documents["168-2024-nd-cp"]["owner_text"]["article_count"] == 55
    for row in documents.values():
        assert row["status"] == "passed"
        assert all(row["checks"].values())
    for key in ("49-vbhn-vpqh", "55-vbhn-vpqh"):
        assert documents[key]["source_docx"]["sha256"] == file_digest(
            PROJECT_ROOT / documents[key]["source_docx"]["path"]
        )
        assert documents[key]["extracted_text"]["sha256"] == file_digest(
            PROJECT_ROOT / documents[key]["extracted_text"]["path"]
        )
    for part in documents["168-2024-nd-cp"]["official_congbao_parts"]:
        assert part["sha256"] == file_digest(PROJECT_ROOT / part["path"])


def test_source_review_normalization_only_removes_pdf_layout_noise():
    assert normalize_legal_text("Mục 1.\nxi-\n lanh") == normalize_legal_text(
        "Mục 1\nxi-lanh"
    )


def test_committed_technical_review_matches_amendment_map():
    record = read_json(PROJECT_ROOT / "data/legal_sources/amendment_review_238_2026.json")
    amendment_path = PROJECT_ROOT / record["amendment_map"]["path"]
    assert record["decision"] == (
        "approved_for_current_law_snapshot_with_publication_blocks"
    )
    assert record["legal_review_status"] == "approved"
    assert record["amendment_map"]["operation_count"] == 102
    assert record["amendment_map"]["target_article_count"] == 24
    assert record["amendment_map"]["sha256_at_review"] == file_digest(amendment_path)
    assert record["locator_audit"]["status"] == "passed"
    assert record["locator_audit"]["passed_operations"] == 102
    assert record["locator_audit"]["failed_operations"] == 0
    assert record["locator_audit"]["sha256_at_review"] == file_digest(
        PROJECT_ROOT / record["locator_audit"]["path"]
    )
    assert record["effective_view"]["status"] == (
        "approved_for_snapshot_freeze"
    )
    assert record["effective_view"]["applied_operation_count"] == 102
    assert record["effective_view"]["sha256_at_review"] == file_digest(
        PROJECT_ROOT / record["effective_view"]["path"]
    )
    assert record["effective_view"]["manifest_sha256_at_review"] == file_digest(
        PROJECT_ROOT / record["effective_view"]["manifest_path"]
    )


def test_current_sources_have_complete_top_level_article_sequences():
    readiness, inventory, amendment_sections, review_packet, markdown = build_reports()
    assert readiness["technical_source_gate_passed"]
    assert readiness["freeze_eligible"]
    assert {row["document_id"]: row["unique_articles"] for row in readiness["structure"]} == {
        "49-vbhn-vpqh": 86,
        "55-vbhn-vpqh": 89,
        "168-2024-nd-cp": 55,
        "238-2026-nd-cp": 21,
    }
    assert readiness["amendment_inventory"]["operation_count"] == 102
    assert readiness["amendment_inventory"]["all_amending_articles_1_to_19_covered"]
    assert not readiness["amendment_inventory"]["unknown_target_articles"]
    assert inventory["legal_as_of"] == "2026-09-22"
    assert [section["amendment_article"] for section in amendment_sections] == list(range(1, 22))
    assert all(section["operation_ids"] for section in amendment_sections[:19])
    assert not amendment_sections[19]["operation_ids"]
    assert len(review_packet["targets"]) == 24
    assert review_packet["targets"][0]["target_article"] == 3
    assert review_packet["targets"][-1]["target_article"] == 55
    assert all(target["operations"] and target["base_section"]["text"] for target in review_packet["targets"])
    assert all(target["review_status"] == "approved" for target in review_packet["targets"])
    assert review_packet["technical_review"]["status"] == "approved"
    assert all(review_packet["technical_review"]["checks"].values())
    assert review_packet["legal_review"]["status"] == "approved"
    assert readiness["locator_audit"]["status"] == "passed"
    assert readiness["effective_view"]["status"] == (
        "approved_for_snapshot_freeze"
    )
    assert readiness["effective_view"]["summary"]["applied_operation_count"] == 102
    assert "không phải effective view" in review_packet["purpose"]
    assert "Production index bị thay đổi: **không**" in markdown
