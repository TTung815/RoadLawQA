"""Trích text xác định từ OOXML, kể cả archive dùng dấu gạch chéo ngược.

Một số DOCX do hệ thống văn bản xuất ra dùng tên ZIP kiểu word\\document.xml.
Microsoft Word vẫn mở được nhưng nhiều thư viện không nhận dạng. Hàm dưới đây
chuẩn hóa tên entry trong bộ nhớ và chỉ đọc phần thân văn bản.
"""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{WORD_NS}}}"


def _archive_members(archive: ZipFile) -> dict[str, str]:
    return {info.filename.replace("\\", "/"): info.filename for info in archive.infolist()}


def _read_xml(path: Path, member_name: str) -> ET.Element | None:
    with ZipFile(path) as archive:
        members = _archive_members(archive)
        actual_name = members.get(member_name)
        if actual_name is None:
            return None
        return ET.fromstring(archive.read(actual_name))


def _paragraph_content(paragraph: ET.Element) -> tuple[str, list[int]]:
    pieces: list[str] = []
    references: list[int] = []
    for node in paragraph.iter():
        if node.tag == W + "t" and node.text:
            pieces.append(node.text)
        elif node.tag == W + "tab":
            pieces.append("\t")
        elif node.tag in {W + "br", W + "cr"}:
            pieces.append("\n")
        elif node.tag == W + "footnoteReference":
            reference_id = node.attrib.get(W + "id")
            if reference_id is not None:
                references.append(int(reference_id))
    text = "".join(pieces).replace("\u00a0", " ")
    return unicodedata.normalize("NFC", text).strip(), references


def extract_document_text(path: Path) -> str:
    """Trả về text phần thân, giữ biên paragraph và bỏ nội dung đã xóa."""
    root = _read_xml(path, "word/document.xml")
    if root is None:
        raise ValueError(f"{path}: không có word/document.xml")

    paragraphs: list[str] = []
    for paragraph in root.iter(W + "p"):
        text, _ = _paragraph_content(paragraph)
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs) + "\n"


def extract_footnote_audit(path: Path) -> dict:
    """Tách footnote và vị trí tham chiếu, không trộn footnote vào body text."""
    document = _read_xml(path, "word/document.xml")
    if document is None:
        raise ValueError(f"{path}: không có word/document.xml")
    footnotes = _read_xml(path, "word/footnotes.xml")

    contexts: dict[int, list[str]] = {}
    for paragraph in document.iter(W + "p"):
        text, references = _paragraph_content(paragraph)
        for reference_id in references:
            contexts.setdefault(reference_id, []).append(text)

    notes: list[dict] = []
    if footnotes is not None:
        for footnote in footnotes.iter(W + "footnote"):
            note_id_text = footnote.attrib.get(W + "id")
            if note_id_text is None or int(note_id_text) <= 0:
                continue
            note_id = int(note_id_text)
            paragraphs = []
            for paragraph in footnote.iter(W + "p"):
                text, _ = _paragraph_content(paragraph)
                if text:
                    paragraphs.append(text)
            notes.append(
                {
                    "footnote_id": note_id,
                    "text": "\n".join(paragraphs),
                    "reference_contexts": contexts.get(note_id, []),
                }
            )

    notes.sort(key=lambda item: item["footnote_id"])
    note_ids = {item["footnote_id"] for item in notes}
    return {
        "schema_version": 1,
        "source_docx": str(path),
        "footnote_count": len(notes),
        "reference_count": sum(len(values) for values in contexts.values()),
        "unresolved_reference_ids": sorted(set(contexts) - note_ids),
        "unreferenced_footnote_ids": sorted(note_ids - set(contexts)),
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Trích text từ phần thân DOCX/OOXML")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--notes-output", type=Path)
    args = parser.parse_args()
    text = extract_document_text(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(f"Đã trích {len(text.splitlines())} dòng vào {args.output}")
    if args.notes_output:
        audit = extract_footnote_audit(args.input)
        args.notes_output.parent.mkdir(parents=True, exist_ok=True)
        args.notes_output.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"Đã trích {audit['footnote_count']} footnote vào {args.notes_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
