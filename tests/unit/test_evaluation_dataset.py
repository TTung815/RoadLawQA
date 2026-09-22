"""Offline regressions for recovery, provenance, gold approval and split safety."""

import copy
import csv
import io
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from evaluation import dataset
from evaluation.dataset_schema import EvaluationCase, require_scoring_gold


@pytest.fixture
def recovery(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_known.py").write_text('QUERY = "Câu hỏi benchmark lịch sử số 1 về xe ô tô?"')
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    dataset.write_json(snapshot / "manifest.json", {"gate_passed": True, "collection_fingerprint": "frozen"})
    props = {"law": "Luật mẫu", "article_no": "1", "clause_no": None, "point": None, "text": "Quy tắc mẫu"}
    dataset.write_json(snapshot / "processed.json", [{"processed_id": "p1", "properties": props}])
    dataset.write_json(snapshot / "id_mapping.json", [{"processed_id": "p1", "runtime_id": "r1", "uuid": "u1", "citation": "Điều 1 Luật mẫu"}])
    monkeypatch.setattr(dataset, "require_trusted_snapshot", lambda s, r: dataset.read_json(s / "manifest.json"))
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(dataset.HEADERS)
    for identity in range(1, 51):
        kind = "tra cứu sự thật" if identity <= 15 else "tra cứu chế tài" if identity <= 30 else "tình huống/suy luận"
        writer.writerow([identity, kind, f"Câu hỏi benchmark lịch sử số {identity} về xe ô tô?", "Đáp án lịch sử, Điều 1 Luật mẫu.\\n"])
    source = tmp_path / "source.csv"
    source.write_bytes(b"\xef\xbb\xbf" + stream.getvalue().encode())
    labels = [{"historical_id": identity, "evidence_groups": [{"id": "g1", "description": "Rule", "processed_ids": ["p1"]}],
               "required_facets": [{"id": "f1", "kind": "rule", "description": "Quy tắc mẫu", "evidence_group_ids": ["g1"]}]}
              for identity in range(1, 51)]
    labels_path = tmp_path / "labels.json"
    dataset.write_json(labels_path, labels)
    return root, source, snapshot, labels_path, tmp_path / "recovered"


def recover_fixture(recovery):
    root, source, snapshot, labels, output = recovery
    dataset.recover(source, snapshot, output, labels, root)
    return dataset.load_cases(output / "cases.jsonl")


def complete_sheet(source: Path) -> bytes:
    reduced = dataset.parse_historical_csv(source.read_bytes())
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(dataset.FULL_HEADERS)
    for index, row in enumerate(reduced):
        history = ["- Khoản 1 Điều 1 Luật số 36/2024/QH15", "Model answer",
                   "" if index == 42 else "- Điều 1", "- Điều 1", "", "1", "0,5", "0.5", "0,66"]
        summary = ["", "", "TỔNG KẾT" if index == 0 else "", "TYPE" if index == 0 else "",
                   "50" if index == 0 else "", "1", "1", "1", "1"]
        writer.writerow([*[row[key] for key in dataset.HEADERS], *history, *summary])
    return stream.getvalue().encode()


def technical_audits() -> list[dict]:
    return [{
        "historical_id": identity,
        "status": "pass",
        "citation_status": "supported",
        "audited_on": "2026-09-22",
        "scope": "Frozen Phase 0 corpus and current V2 publication policy.",
        "recommended_answer": f"Đáp án đề xuất cho câu {identity}.",
        "recommended_coverage": "sufficient",
        "recommended_publication": {
            "disposition": "publish",
            "allowed_statuses": ["answered"],
            "rationale": "Evidence đóng băng hỗ trợ đáp án đề xuất.",
        },
        "findings": [],
        "external_sources": [],
    } for identity in range(1, 51)]


def test_recovery_preserves_bytes_raw_rows_and_ids(recovery):
    cases = recover_fixture(recovery)
    root, source, snapshot, _, output = recovery
    assert (output / "source.csv").read_bytes() == source.read_bytes()
    assert cases[0].source.raw_fields["Gold_answer"].endswith("\\n")
    assert not cases[0].legacy_answer.endswith("\\n")
    assert [case.id for case in cases] == [f"legacy_{i:03d}" for i in range(1, 51)]
    assert all(case.split == "legacy" and case.exposure == "historically_used" for case in cases)
    assert all(case.gold.review.status == "needs_review" for case in cases)
    report = dataset.audit_bundle(output, snapshot, root)
    assert report["dataset_integrity_passed"] and not report["official_scoring_ready"]
    assert report["query_types"] == {"factual": 15, "penalty": 15, "scenario": 20}
    assert report["regression_overlap_candidates"][0]["case_id"] == "legacy_001"
    with pytest.raises(ValueError, match="Gold is not approved"):
        require_scoring_gold(cases)


def test_complete_sheet_preserves_citations_run_observations_and_decimal_commas(recovery):
    root, source, snapshot, labels, output = recovery
    source.write_bytes(complete_sheet(source))
    report = dataset.recover(source, snapshot, output, labels, root, dataset_id="historical_50_v2",
                             source_url="https://docs.google.com/example")
    cases = dataset.load_cases(output / "cases.jsonl")
    assert cases[0].legacy_gold_citations == ["Khoản 1 Điều 1 Luật số 36/2024/QH15"]
    assert cases[0].historical_run.legal_citation == .5
    assert cases[0].historical_run.total_score == .66
    assert cases[42].historical_run.model_citations_raw is None
    assert report["historical_gold_citation_cases"] == 50
    assert report["historical_gold_citation_count"] == 50
    assert report["historical_run_records"] == 50
    assert dataset.read_json(output / "manifest.json")["source_url"] == "https://docs.google.com/example"


def test_complete_sheet_requires_gold_citation_but_allows_missing_model_citation(recovery):
    _, source, _, _, _ = recovery
    payload = complete_sheet(source)
    rows = list(csv.reader(io.StringIO(payload.decode()), strict=True))
    rows[1][4] = ""
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    with pytest.raises(ValueError, match="history cell"):
        dataset.parse_historical_csv(stream.getvalue().encode())


def test_technical_audit_is_versioned_and_counted_without_approving_gold(recovery):
    root, source, snapshot, labels, output = recovery
    source.write_bytes(complete_sheet(source))
    audits_path = recovery[-1].parent / "technical_audit.json"
    dataset.write_json(audits_path, technical_audits())
    report = dataset.recover(source, snapshot, output, labels, root,
                             dataset_id="historical_50_v3", technical_audit_path=audits_path)
    cases = dataset.load_cases(output / "cases.jsonl")
    assert report["technical_audit_cases"] == 50
    assert report["technical_audit_status"] == {"pass": 50}
    assert all(case.gold.technical_audit is not None for case in cases)
    assert all(case.gold.review.status == "needs_review" for case in cases)
    assert "technical_audit.json" in dataset.read_json(output / "manifest.json")["artifacts"]
    assert dataset.audit_bundle(output, snapshot, root)["technical_audit_cases"] == 50
    with (output / "technical_audit.json").open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="artifact changed"):
        dataset.audit_bundle(output, snapshot, root)


def test_technical_audit_requires_exact_identity_coverage(recovery):
    _, source, snapshot, labels, _ = recovery
    rows = dataset.parse_historical_csv(source.read_bytes())
    with pytest.raises(ValueError, match="cover 1..50"):
        dataset.recover_cases(rows, source.name, dataset.file_digest(source), snapshot,
                              dataset.read_json(labels), technical_audits()[:-1])


def test_invalid_technical_audit_fails_before_writing_bundle(recovery):
    root, source, snapshot, labels, output = recovery
    audits = technical_audits()
    audits[0]["status"] = "approved"
    audits_path = output.parent / "invalid_technical_audit.json"
    dataset.write_json(audits_path, audits)
    with pytest.raises(ValidationError):
        dataset.recover(source, snapshot, output, labels, root, technical_audit_path=audits_path)
    assert not output.exists()


def test_historical_citation_mapping_is_audited(recovery):
    cases = recover_fixture(recovery)
    root, _, snapshot, _, _ = recovery
    data = cases[0].model_dump()
    data["legacy_gold_citations"] = ["Khoản 2 Điều 99 Luật số 36/2024/QH15"]
    report = dataset.audit_cases([EvaluationCase.model_validate(data), *cases[1:]], snapshot, root)
    assert report["historical_gold_citations_unmapped"][0]["case_id"] == "legacy_001"


@pytest.mark.parametrize("change", ["short", "duplicate", "empty", "extra", "type", "headers", "noncanonical"])
def test_csv_invalid_records_are_rejected(recovery, change):
    _, source, _, _, _ = recovery
    rows = dataset.parse_historical_csv(source.read_bytes())
    headers = dataset.HEADERS
    if change == "short": rows.pop()
    elif change == "duplicate": rows[1]["STT"] = "1"
    elif change == "empty": rows[0]["Question"] = " "
    elif change == "type": rows[0]["Type"] = "unknown"
    elif change == "headers": headers = ["ID", *headers[1:]]
    elif change == "noncanonical": rows[0]["STT"] = "01"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers)
    for i, row in enumerate(rows):
        values = [row[key] for key in dataset.HEADERS]
        if change == "extra" and i == 0: values.append("unexpected")
        writer.writerow(values)
    with pytest.raises(ValueError):
        dataset.parse_historical_csv(stream.getvalue().encode())


def test_csv_reordered_rows_keep_historical_identity(recovery):
    _, source, snapshot, labels, _ = recovery
    rows = dataset.parse_historical_csv(source.read_bytes())[::-1]
    cases = dataset.recover_cases(rows, "source.csv", dataset.file_digest(source), snapshot, dataset.read_json(labels))
    assert cases[0].id == "legacy_050" and cases[0].source.csv_record == 2


def test_missing_evidence_never_becomes_gold(recovery):
    root, source, snapshot, labels, output = recovery
    data = dataset.read_json(labels)
    data[0]["evidence_groups"][0]["processed_ids"] = ["missing"]
    dataset.write_json(labels, data)
    with pytest.raises(ValueError, match="absent from frozen"):
        dataset.recover(source, snapshot, output, labels, root)
    assert not output.exists()


def test_duplicate_normalized_questions_block_recovery(recovery):
    root, source, snapshot, labels, output = recovery
    rows = dataset.parse_historical_csv(source.read_bytes())
    rows[1]["Question"] = "  " + rows[0]["Question"].upper() + "  "
    with source.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=dataset.HEADERS)
        writer.writeheader(); writer.writerows(rows)
    with pytest.raises(ValueError, match="integrity audit"):
        dataset.recover(source, snapshot, output, labels, root)
    assert not output.exists()


def test_recovery_refuses_overwrite(recovery):
    recover_fixture(recovery)
    root, source, snapshot, labels, output = recovery
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError):
        dataset.recover(source, snapshot, output, labels, root)
    assert (output / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("artifact", ["source.csv", "cases.jsonl", "draft_labels.json", "case.schema.json"])
def test_modified_artifact_blocks_audit(recovery, artifact):
    recover_fixture(recovery)
    root, _, snapshot, _, output = recovery
    with (output / artifact).open("a") as stream: stream.write(" ")
    with pytest.raises(ValueError, match="artifact changed"):
        dataset.audit_bundle(output, snapshot, root)


def test_different_snapshot_blocks_audit(recovery):
    recover_fixture(recovery)
    root, _, snapshot, _, output = recovery
    dataset.write_json(snapshot / "manifest.json", {"gate_passed": True, "collection_fingerprint": "new"})
    with pytest.raises(ValueError, match="different baseline"):
        dataset.audit_bundle(output, snapshot, root)


def test_reference_and_source_row_validation_independent_of_inventory(recovery):
    cases = recover_fixture(recovery)
    root, _, snapshot, _, output = recovery
    data = cases[0].model_dump()
    data["gold"]["evidence_groups"][0]["references"][0]["runtime_id"] = "wrong"
    changed = EvaluationCase.model_validate(data)
    report = dataset.audit_cases([changed, *cases[1:]], snapshot, root)
    assert not report["dataset_integrity_passed"]
    data = cases[0].model_dump()
    data["source"]["raw_fields"]["Question"] = "Changed"
    changed = EvaluationCase.model_validate(data)
    (output / "cases.jsonl").write_text("".join(case.model_dump_json() + "\n" for case in [changed,*cases[1:]]))
    manifest = dataset.read_json(output / "manifest.json")
    manifest["artifacts"]["cases.jsonl"] = dataset.file_digest(output / "cases.jsonl")
    dataset.write_json(output / "manifest.json", manifest)
    with pytest.raises(ValueError, match="historical source row"):
        dataset.audit_bundle(output, snapshot, root)


@pytest.mark.parametrize("mutation", ["held_out", "unknown_group", "category", "approve_without_review", "negative_publish", "context_publish"])
def test_gold_rejects_leakage_and_unsupported_approval(recovery, mutation):
    case = recover_fixture(recovery)[0].model_dump()
    if mutation == "held_out": case["split"] = "held_out"
    elif mutation == "unknown_group": case["gold"]["required_facets"][0]["evidence_group_ids"] = ["missing"]
    elif mutation == "category": case["gold"]["failure_categories"] = ["invented"]
    else:
        gold = case["gold"]
        gold["review"]["status"] = "approved"
        if mutation != "approve_without_review":
            gold["review"].update(reviewer="owner", reviewed_on="2026-09-18")
            gold.update(temporal_basis="frozen_corpus", expected_coverage="sufficient", reference_answer="Quy tắc mẫu")
            gold["publication"].update(disposition="publish",allowed_statuses=["answered"])
            gold["required_facets"][0]["support_state"] = "positive_support"
            if mutation == "negative_publish": gold["required_facets"][0]["support_state"] = "negative_support"
            else: gold["evidence_groups"][0]["references"][0]["role"] = "context"
    with pytest.raises(ValidationError): EvaluationCase.model_validate(case)


def test_reviewed_positive_gold_and_abstention_are_scorable(recovery):
    data = recover_fixture(recovery)[0].model_dump()
    gold = data["gold"]
    gold["review"].update(status="approved",reviewer="owner", reviewed_on="2026-09-18")
    gold.update(temporal_basis="frozen_corpus", expected_coverage="sufficient", reference_answer="Quy tắc mẫu")
    gold["publication"].update(disposition="publish",allowed_statuses=["answered"])
    gold["required_facets"][0]["support_state"] = "positive_support"
    approved = EvaluationCase.model_validate(data)
    require_scoring_gold([approved])
    abstain = copy.deepcopy(data)
    abstain["id"] = "legacy_002"
    abstain["gold"]["publication"].update(disposition="abstain",allowed_statuses=["insufficient_evidence"])
    abstain["gold"].update(reference_answer=None,expected_coverage="insufficient")
    abstain["gold"]["required_facets"][0]["support_state"] = "unknown"
    require_scoring_gold([EvaluationCase.model_validate(abstain)])


def test_scoring_rejects_empty_duplicate_and_excluded_cases(recovery):
    case = recover_fixture(recovery)[0]
    with pytest.raises(ValueError): require_scoring_gold([])
    with pytest.raises(ValueError): require_scoring_gold([case,case])
    data = case.model_dump()
    data["gold"]["review"].update(status="excluded",notes=["Source unresolved"])
    with pytest.raises(ValueError,match="not approved"):
        require_scoring_gold([EvaluationCase.model_validate(data)])
