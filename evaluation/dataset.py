"""CSV parsing retained for current-law dataset provenance; V1 audit CLI retired."""

import ast
import csv
import io
from pathlib import Path
import re
import unicodedata
from evaluation.snapshot import PROJECT_ROOT

HEADERS = ["STT", "Type", "Question", "Gold_answer"]
FULL_HEADERS = ["STT", "Type", "Question", "Gold_answer", "Gold_citations", "Model_answer",
                "Model_citations", "retriever_sources", "", "Legal_accuracy", "Legal_citation",
                "Relevance", "Total Score", "", "", "TỔNG KẾT", "TYPE", "SỐ CÂU HỎI",
                "LEGAL ACCURACY", "LEGAL CITATION", "RELEVANCE", "SCORES"]
RUN_FIELDS = ("Gold_citations", "Model_answer", "Model_citations", "retriever_sources",
              "Legal_accuracy", "Legal_citation", "Relevance", "Total Score")
QUERY_TYPES = {"tra cứu sự thật": "factual", "tra cứu chế tài": "penalty", "tình huống/suy luận": "scenario"}


def normalize_text(text: str) -> str:
    # CSV contains both actual newlines and literal escaped export newlines.
    text = text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
    return unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n")).strip()

def question_key(text: str) -> str:
    return " ".join(normalize_text(text).casefold().split())

def parse_historical_csv(payload: bytes) -> list[dict[str, str]]:
    records = list(csv.reader(io.StringIO(payload.decode("utf-8-sig"), newline=""), strict=True))
    if not records:
        raise ValueError("Historical CSV is empty")
    header, values = records[0], records[1:]
    if header not in (HEADERS, FULL_HEADERS):
        raise ValueError("Expected the reduced 4-column or complete 22-column historical sheet")
    if any(len(row) != len(header) for row in values):
        raise ValueError("Historical CSV row width differs from its header")
    fields = HEADERS if header == HEADERS else [*HEADERS, *RUN_FIELDS]
    positions = list(range(4)) if header == HEADERS else [0, 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12]
    rows = [{field: row[position] for field, position in zip(fields, positions)} for row in values]
    if len(rows) != 50:
        raise ValueError(f"Historical recovery requires exactly 50 records, found {len(rows)}")
    ids = []
    for row in rows:
        if not all(isinstance(row.get(key), str) and row[key].strip() for key in HEADERS):
            raise ValueError("CSV has a missing or empty core cell")
        required_history = ("Gold_citations", "Model_answer", "retriever_sources",
                            "Legal_accuracy", "Legal_citation", "Relevance", "Total Score")
        if header == FULL_HEADERS and any(not row[key].strip() for key in required_history):
            raise ValueError("Complete historical sheet has a missing required history cell")
        identity = row["STT"].strip()
        if not identity.isascii() or not identity.isdigit() or str(int(identity)) != identity:
            raise ValueError("Historical IDs must be canonical integers")
        ids.append(int(identity))
        if normalize_text(row["Type"]) not in QUERY_TYPES:
            raise ValueError(f"Unknown historical question type: {row['Type']}")
    if sorted(ids) != list(range(1, 51)):
        raise ValueError("Historical IDs must contain 1..50 exactly once")
    return rows

def parse_citations(raw: str) -> list[str]:
    citations = []
    for line in normalize_text(raw).splitlines():
        value = re.sub(r"^\s*-\s*", "", line).strip()
        value = value.strip("[]").strip().strip('"').strip()
        if value:
            citations.append(value)
    return citations

def parse_score(value: str) -> float:
    return float(value.strip().replace(",", "."))

def historical_run(row: dict[str, str]):
    if "Model_answer" not in row:
        return None
    return {"model_answer": normalize_text(row["Model_answer"]),
            "model_citations_raw": normalize_text(row["Model_citations"]) or None,
            "retriever_sources_raw": normalize_text(row["retriever_sources"]),
            "legal_accuracy": parse_score(row["Legal_accuracy"]),
            "legal_citation": parse_score(row["Legal_citation"]),
            "relevance": parse_score(row["Relevance"]),
            "total_score": parse_score(row["Total Score"])}

def regression_strings(root: Path) -> list[tuple[str, str]]:
    """Overlap candidates only: string similarity is not proof of semantic leakage."""
    strings = []
    for path in sorted((root / "tests").rglob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and 25 <= len(node.value) <= 1500:
                strings.append((str(path.relative_to(root)), question_key(node.value)))
    return strings
