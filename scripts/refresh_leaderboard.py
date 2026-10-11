#!/usr/bin/env python3
"""Fetch and validate the public DrivenData leaderboard for the Pages status feed.

This script records public leaderboard rows only. It does not authenticate, submit a file,
attribute a row to a TIFF, or create an organizer receipt. If the page layout changes or the
parsed rows fail validation, it exits without replacing the previously published JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

SOURCE_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
EVIDENCE_LABEL = (
    "PUBLIC-LEADERBOARD-OBSERVATION (official organizer page only; not a submission-page "
    "receipt, not linked to a named TIFF, and excluded from receipt-backed score evidence)."
)


class _TableParser(HTMLParser):
    """Small standard-library table reader; retains <br> boundaries in cells."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
        elif self._table_depth and tag == "tr":
            self._row = []
        elif self._table_depth and self._row is not None and tag in {"td", "th"}:
            self._cell = []
        elif self._table_depth and self._cell is not None and tag in {"br", "p", "div"}:
            self._cell.append("\n")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._table_depth and tag in {"td", "th"} and self._cell is not None:
            text = "".join(self._cell)
            normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
            if self._row is not None:
                self._row.append(normalized)
            self._cell = None
        elif self._table_depth and tag == "tr" and self._row is not None:
            if self._row and self._table is not None:
                self._table.append(self._row)
            self._row = None
            self._cell = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._table is not None:
                self.tables.append(self._table)
                self._table = None
                self._row = None
                self._cell = None


def _header_indexes(table: list[list[str]]) -> tuple[int, int, int, int] | None:
    for row_index, row in enumerate(table):
        lowered = [re.sub(r"\s+", " ", cell).strip().lower() for cell in row]
        rank_index = next((i for i, cell in enumerate(lowered) if cell == "rank"), None)
        participant_index = next((i for i, cell in enumerate(lowered) if "participant" in cell), None)
        score_index = next(
            (i for i, cell in enumerate(lowered) if "tversky" in cell or ("best" in cell and "public" in cell)),
            None,
        )
        if rank_index is not None and participant_index is not None and score_index is not None:
            return row_index, rank_index, participant_index, score_index
    return None


def parse_leaderboard_html(html: str, retrieved_at_utc: str | None = None) -> dict:
    parser = _TableParser()
    parser.feed(html)
    found = None
    for table in parser.tables:
        indexes = _header_indexes(table)
        if indexes:
            found = (table, indexes)
            break
    if found is None:
        raise ValueError("Could not locate the official leaderboard table headers")

    table, (header_row, rank_i, participant_i, score_i) = found
    rows = []
    seen_ranks: set[int] = set()
    for cells in table[header_row + 1 :]:
        if max(rank_i, participant_i, score_i) >= len(cells):
            continue
        rank_match = re.fullmatch(r"#?\s*(\d+)\s*", cells[rank_i])
        if not rank_match:
            continue
        rank = int(rank_match.group(1))
        participant_lines = [line.strip() for line in cells[participant_i].splitlines() if line.strip()]
        participant = participant_lines[0] if participant_lines else ""
        score = re.sub(r"\s+", "", cells[score_i])
        if not participant:
            raise ValueError(f"Leaderboard row {rank} has no participant name")
        if not re.fullmatch(r"(?:0(?:\.\d+)?|1(?:\.0+)?)", score):
            raise ValueError(f"Leaderboard row {rank} has an invalid public DTI value: {score!r}")
        if rank in seen_ranks:
            raise ValueError(f"Duplicate leaderboard rank: {rank}")
        seen_ranks.add(rank)
        rows.append({"rank": rank, "participant": participant, "public_dti": score})

    if not rows:
        raise ValueError("The leaderboard table was found, but it contained no validated rows")
    rows.sort(key=lambda item: item["rank"])
    if len(rows) != len(seen_ranks):  # explicit invariant; protects future parser edits
        raise ValueError("Leaderboard rows failed rank uniqueness validation")

    timestamp = retrieved_at_utc or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "retrieved_at_utc": timestamp,
        "source_url": SOURCE_URL,
        "feed_type": "official public leaderboard snapshot",
        "refresh_status": "refreshed",
        "evidence_label": EVIDENCE_LABEL,
        "receipt_available": False,
        "eligible_as_artifact_score_evidence": False,
        "snapshot_scope": "Rows parsed from the public leaderboard page at retrieval time; values can change and do not identify uploaded TIFF filenames.",
        "rows": rows,
    }


def _fetch_html() -> str:
    request = Request(SOURCE_URL, headers={"User-Agent": "GEMSDOE65 public leaderboard feed/1.0"})
    with urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Leaderboard fetch returned HTTP {response.status}")
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".tmp")
    try:
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("docs/data/leaderboard.json"))
    parser.add_argument("--html", type=Path, help="parse a saved HTML page instead of fetching the public page")
    args = parser.parse_args(argv)
    try:
        html = args.html.read_text(encoding="utf-8", errors="replace") if args.html else _fetch_html()
        result = parse_leaderboard_html(html)
        write_json_atomic(args.output, result)
    except Exception as exc:  # fail closed: do not overwrite the last verified snapshot
        print(f"leaderboard refresh failed; existing snapshot was not replaced: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {len(result['rows'])} public leaderboard rows to {args.output}")
    print("No submission-page receipt or TIFF attribution is created by this feed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
