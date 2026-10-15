"""Kiểm tra registry nguồn pháp luật và gate đóng băng corpus hiện hành.

Module này chỉ đọc artifact và tạo báo cáo. Nó không tải dữ liệu, không sửa
collection Weaviate và không thay pipeline production.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PROJECT_ROOT / "data/legal_sources/registry.json"
DEFAULT_AMENDMENTS = PROJECT_ROOT / "data/legal_sources/amendments_238_2026.json"


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Review(RegistryModel):
    status: Literal["pending", "approved", "rejected"] = "pending"
    reviewer: str | None = None
    reviewed_on: date | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def approval_has_identity(self):
        if self.status == "approved" and (not self.reviewer or not self.reviewed_on):
            raise ValueError("Review được duyệt phải có reviewer và ngày duyệt")
        return self


class SourceArtifact(RegistryModel):
    landing_url: str
    attachment_url: str | None = None
    raw_path: str | None = None
    sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    media_type: str | None = None
    pages: int | None = Field(default=None, ge=1)
    acquired_on: date | None = None


class Extraction(RegistryModel):
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    method: str
    tool_version: str
    quality: Literal[
        "text_layer",
        "ocr",
        "legacy_text_verified_against_pdf",
        "user_provided_text",
        "docx_supporting_text",
        "official_docx_text",
    ]
    supporting_input_path: str | None = None
    supporting_input_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    supporting_input_origin: str | None = None
    supporting_input_url: str | None = None
    review: Review = Field(default_factory=Review)
    notes: list[str] = Field(default_factory=list)


class Relation(RegistryModel):
    type: Literal["consolidates", "amends", "base_of", "lineage"]
    target_document_id: str
    notes: str | None = None


class ScopeDecision(RegistryModel):
    decision: Literal["ingest", "metadata_only", "excluded"]
    reason: str
    included_sections: list[str] = Field(default_factory=list)


class LegalDocument(RegistryModel):
    document_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]+$")
    symbol: str
    title: str
    document_type: Literal["luat", "nghi_dinh", "van_ban_hop_nhat"]
    issuing_authority: str
    issued_on: date
    effective_from: date | None = None
    effective_to: date | None = None
    status_at_cutoff: Literal["effective", "official_consolidation", "lineage_only"]
    roles: list[Literal["canonical", "base", "amending", "dependency", "historical"]]
    source: SourceArtifact
    extraction: Extraction | None = None
    relations: list[Relation] = Field(default_factory=list)
    scope: ScopeDecision
    temporal_notes: list[str] = Field(default_factory=list)
    metadata_review: Review = Field(default_factory=Review)

    @model_validator(mode="after")
    def artifact_contract(self):
        if self.scope.decision == "ingest":
            if not self.source.raw_path or not self.source.sha256:
                raise ValueError(f"{self.document_id}: nguồn ingest thiếu path/hash")
            if self.extraction is None:
                raise ValueError(f"{self.document_id}: nguồn ingest thiếu extraction")
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValueError(f"{self.document_id}: khoảng hiệu lực không hợp lệ")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError(f"{self.document_id}: role bị trùng")
        return self


class Registry(RegistryModel):
    schema_version: Literal[1]
    registry_id: str
    legal_as_of: date
    jurisdiction: str
    source_policy: str
    scope_document: str
    scope_review: Review
    documents: list[LegalDocument]

    @model_validator(mode="after")
    def registry_contract(self):
        ids = [document.document_id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("document_id trong registry phải duy nhất")
        known = set(ids)
        for document in self.documents:
            for relation in document.relations:
                if relation.target_document_id not in known:
                    raise ValueError(
                        f"{document.document_id}: relation trỏ tới document không tồn tại "
                        f"{relation.target_document_id}"
                    )
        required = {
            "49-vbhn-vpqh",
            "55-vbhn-vpqh",
            "168-2024-nd-cp",
            "238-2026-nd-cp",
        }
        if not required <= known:
            raise ValueError(f"Registry thiếu nguồn lõi: {sorted(required - known)}")
        return self


class AmendmentOperation(RegistryModel):
    operation_id: str
    amendment_article: int = Field(ge=1, le=19)
    operation: Literal[
        "add",
        "add_phrase",
        "replace",
        "replace_phrase",
        "remove_phrase",
        "repeal",
    ]
    target_article: int = Field(ge=1)
    target_clause: str | None = Field(default=None, pattern=r"^\d+[a-z]?$")
    target_point: str | None = Field(default=None, pattern=r"^[a-zđ]\d?$")
    source_pages: list[int] = Field(min_length=1)
    effective_from: date
    review_status: Literal["pending", "approved", "blocking"]
    notes: str


class AmendmentMap(RegistryModel):
    schema_version: Literal[1]
    map_id: str
    base_document_id: str
    amending_document_id: str
    legal_as_of: date
    interpretation: Literal["overlay_on_base"]
    operations: list[AmendmentOperation]
    legal_review: Review

    @model_validator(mode="after")
    def amendment_contract(self):
        ids = [operation.operation_id for operation in self.operations]
        if len(ids) != len(set(ids)):
            raise ValueError("operation_id trong amendment map phải duy nhất")
        covered = {operation.amendment_article for operation in self.operations}
        missing = set(range(1, 20)) - covered
        if missing:
            raise ValueError(f"Chưa kiểm kê Điều sửa đổi: {sorted(missing)}")
        return self


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _check_artifact(project_root: Path, relative_path: str | None, expected: str | None) -> dict:
    if not relative_path or not expected:
        return {"path": relative_path, "required": False, "passed": True}
    path = project_root / relative_path
    actual = file_digest(path) if path.is_file() else None
    return {
        "path": relative_path,
        "required": True,
        "exists": path.is_file(),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "passed": actual == expected,
    }


def audit_registry(
    project_root: Path = PROJECT_ROOT,
    registry_path: Path = DEFAULT_REGISTRY,
    amendments_path: Path = DEFAULT_AMENDMENTS,
) -> dict:
    registry = Registry.model_validate(read_json(registry_path))
    amendments = AmendmentMap.model_validate(read_json(amendments_path))
    known = {document.document_id for document in registry.documents}
    if amendments.base_document_id not in known or amendments.amending_document_id not in known:
        raise ValueError("Amendment map trỏ tới document ngoài registry")
    if amendments.legal_as_of != registry.legal_as_of:
        raise ValueError("legal_as_of của registry và amendment map không khớp")

    checks: list[dict] = []
    for document in registry.documents:
        checks.append(
            {
                "document_id": document.document_id,
                "kind": "official_source",
                **_check_artifact(project_root, document.source.raw_path, document.source.sha256),
            }
        )
        if document.extraction:
            checks.append(
                {
                    "document_id": document.document_id,
                    "kind": "extraction",
                    **_check_artifact(project_root, document.extraction.path, document.extraction.sha256),
                }
            )
            if document.extraction.supporting_input_path:
                checks.append(
                    {
                        "document_id": document.document_id,
                        "kind": "supporting_input",
                        **_check_artifact(
                            project_root,
                            document.extraction.supporting_input_path,
                            document.extraction.supporting_input_sha256,
                        ),
                    }
                )

    artifact_integrity_passed = all(check["passed"] for check in checks)
    pending_documents = [
        document.document_id
        for document in registry.documents
        if document.scope.decision == "ingest"
        and (
            document.metadata_review.status != "approved"
            or not document.extraction
            or document.extraction.review.status != "approved"
        )
    ]
    blocking_operations = [
        operation.operation_id
        for operation in amendments.operations
        if operation.review_status != "approved"
    ]
    freeze_eligible = (
        artifact_integrity_passed
        and registry.scope_review.status == "approved"
        and not pending_documents
        and amendments.legal_review.status == "approved"
        and not blocking_operations
    )
    return {
        "schema_version": 1,
        "registry_id": registry.registry_id,
        "legal_as_of": registry.legal_as_of.isoformat(),
        "registry_sha256": file_digest(registry_path),
        "amendment_map_sha256": file_digest(amendments_path),
        "artifact_integrity_passed": artifact_integrity_passed,
        "freeze_eligible": freeze_eligible,
        "scope_review_status": registry.scope_review.status,
        "pending_documents": pending_documents,
        "blocking_amendment_operations": blocking_operations,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit registry nguồn pháp luật hiện hành")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--amendments", type=Path, default=DEFAULT_AMENDMENTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = audit_registry(PROJECT_ROOT, args.registry, args.amendments)
    if args.output:
        write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["freeze_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
