#!/usr/bin/env python3
"""
CSV PII Redactor — Redacts personal and business data from CSV files.

All processing happens locally. No data leaves the machine.

Usage:
    python redact_csv.py tickets.csv
    python redact_csv.py tickets.csv -o clean.csv
    python redact_csv.py tickets.csv --dry-run
"""

import argparse
import csv
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider


# ---------------------------------------------------------------------------
# PII entity types to detect
# ---------------------------------------------------------------------------

ENTITIES = [
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IP_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "US_SSN",
    "URL",
    "NRP",            # nationality / religious / political group
]

# Friendly names for the report
ENTITY_LABELS = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORGANIZATION",
    "LOCATION": "LOCATION",
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER": "PHONE",
    "IP_ADDRESS": "IP_ADDRESS",
    "CREDIT_CARD": "CREDIT_CARD",
    "IBAN_CODE": "IBAN",
    "US_SSN": "SSN",
    "URL": "URL",
    "NRP": "NRP",
    "HOSTNAME": "HOSTNAME",
    "MAC_ADDRESS": "MAC_ADDRESS",
}


# ---------------------------------------------------------------------------
# Custom recognizers for infra PII that presidio doesn't cover
# ---------------------------------------------------------------------------

def _build_custom_recognizers():
    """Extra patterns for MSP / IT ticket data."""
    recognizers = []

    # Hostnames like srv-prod-01.internal, fw-gw-01.domain.local
    recognizers.append(PatternRecognizer(
        supported_entity="HOSTNAME",
        name="hostname_recognizer",
        patterns=[Pattern(
            name="hostname",
            regex=(
                r"\b(?:[a-zA-Z0-9-]+\.)*"
                r"(?:srv|host|node|dc|gw|fw|db|app|web|mail|vpn)"
                r"[a-zA-Z0-9]*"
                r"(?:[.\-][a-zA-Z0-9.\-]+)+\b"
            ),
            score=0.7,
        )],
    ))

    # MAC addresses
    recognizers.append(PatternRecognizer(
        supported_entity="MAC_ADDRESS",
        name="mac_address_recognizer",
        patterns=[Pattern(
            name="mac_address",
            regex=r"\b(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b",
            score=0.85,
        )],
    ))

    # International phone numbers — presidio's built-in misses many formats
    recognizers.append(PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        name="intl_phone_recognizer",
        patterns=[
            Pattern(
                name="intl_phone",
                regex=r"\+\d{1,3}[\s.\-]?\d[\d\s.\-]{5,15}\d",
                score=0.95,
            ),
            Pattern(
                name="domestic_phone",
                regex=r"\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}",
                score=0.9,
            ),
        ],
    ))

    return recognizers


# ---------------------------------------------------------------------------
# Analyzer setup
# ---------------------------------------------------------------------------

def create_analyzer() -> AnalyzerEngine:
    provider = NlpEngineProvider(nlp_configuration={
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    })
    nlp_engine = provider.create_engine()

    analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])

    for recognizer in _build_custom_recognizers():
        analyzer.registry.add_recognizer(recognizer)

    return analyzer


# ---------------------------------------------------------------------------
# Deterministic placeholder generator
# ---------------------------------------------------------------------------

class PlaceholderMap:
    """Maps original values to stable placeholders like [EMAIL-1], [EMAIL-2]."""

    def __init__(self):
        self._maps: dict[str, dict[str, str]] = defaultdict(dict)
        self._counters: dict[str, int] = defaultdict(int)
        self.stats: dict[str, int] = defaultdict(int)

    def get(self, category: str, original: str) -> str:
        label = ENTITY_LABELS.get(category, category)
        key = original.strip().lower()
        if key not in self._maps[label]:
            self._counters[label] += 1
            self._maps[label][key] = f"[{label}-{self._counters[label]}]"
        self.stats[label] += 1
        return self._maps[label][key]

    def unique_counts(self) -> dict[str, int]:
        return {cat: len(vals) for cat, vals in self._maps.items() if vals}


# ---------------------------------------------------------------------------
# Cell redaction
# ---------------------------------------------------------------------------

def redact_cell(text: str, analyzer: AnalyzerEngine, pmap: PlaceholderMap) -> str:
    if not text or not text.strip():
        return text

    all_entities = ENTITIES + ["HOSTNAME", "MAC_ADDRESS"]

    results = analyzer.analyze(
        text=text,
        language="en",
        entities=all_entities,
        score_threshold=0.4,
    )

    if not results:
        return text

    # Deduplicate overlapping spans — prefer longer span, then higher score
    results = sorted(results, key=lambda r: r.start)
    filtered = []
    for r in results:
        if filtered and r.start < filtered[-1].end:
            # Overlap: keep the longer span; if same length, keep higher score
            prev = filtered[-1]
            prev_len = prev.end - prev.start
            curr_len = r.end - r.start
            if curr_len > prev_len or (curr_len == prev_len and r.score > prev.score):
                filtered[-1] = r
        else:
            filtered.append(r)
    # Reverse for descending start so replacements don't shift indices
    results = list(reversed(filtered))

    for result in results:
        original = text[result.start:result.end]
        placeholder = pmap.get(result.entity_type, original)
        text = text[:result.start] + placeholder + text[result.end:]

    return text


# ---------------------------------------------------------------------------
# CSV processing
# ---------------------------------------------------------------------------

def detect_dialect(file_path: str) -> csv.Dialect:
    with open(file_path, "r", newline="", encoding="utf-8-sig") as f:
        sample = f.read(8192)
    try:
        return csv.Sniffer().sniff(sample)
    except csv.Error:
        return csv.excel


def process_csv(
    input_path: str,
    output_path: str,
    dry_run: bool = False,
) -> dict:
    pmap = PlaceholderMap()
    dialect = detect_dialect(input_path)

    print("Loading NLP model...", file=sys.stderr)
    analyzer = create_analyzer()

    # Read all rows
    with open(input_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f, dialect)
        header = next(reader)
        rows = list(reader)

    total_rows = len(rows)
    total_cells = 0
    redacted_cells = 0

    print(f"Processing {total_rows} rows, {len(header)} columns...", file=sys.stderr)
    start_time = time.time()

    redacted_rows = []
    report_interval = max(1, total_rows // 20)

    for row_idx, row in enumerate(rows):
        new_row = []
        for cell in row:
            total_cells += 1
            original = cell
            cell = redact_cell(cell, analyzer, pmap)
            if cell != original:
                redacted_cells += 1
            new_row.append(cell)
        redacted_rows.append(new_row)

        if (row_idx + 1) % report_interval == 0 or row_idx == total_rows - 1:
            pct = int((row_idx + 1) / total_rows * 100)
            print(f"  {pct}% ({row_idx + 1}/{total_rows} rows)", file=sys.stderr)

    elapsed = time.time() - start_time

    # Write output
    if not dry_run:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, dialect)
            writer.writerow(header)
            writer.writerows(redacted_rows)

    # Build report
    report = {
        "input_file": input_path,
        "output_file": output_path if not dry_run else "(dry run - not written)",
        "total_rows": total_rows,
        "total_cells": total_cells,
        "cells_redacted": redacted_cells,
        "elapsed_seconds": round(elapsed, 2),
        "detections_by_type": dict(pmap.stats),
        "unique_values_by_type": pmap.unique_counts(),
    }
    return report


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def print_report(report: dict):
    print("\n" + "=" * 60, file=sys.stderr)
    print("  REDACTION REPORT", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print(f"  Input:          {report['input_file']}", file=sys.stderr)
    print(f"  Output:         {report['output_file']}", file=sys.stderr)
    print(f"  Rows processed: {report['total_rows']}", file=sys.stderr)
    print(f"  Cells scanned:  {report['total_cells']}", file=sys.stderr)
    print(f"  Cells redacted: {report['cells_redacted']}", file=sys.stderr)
    print(f"  Time:           {report['elapsed_seconds']}s", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    detections = report["detections_by_type"]
    uniques = report["unique_values_by_type"]
    if detections:
        print("  Detections:", file=sys.stderr)
        for category in sorted(detections.keys()):
            total = detections[category]
            unique = uniques.get(category, 0)
            print(f"    {category:<20s} {total:>6d} found  ({unique} unique)", file=sys.stderr)
    else:
        print("  No PII detected.", file=sys.stderr)

    print("=" * 60 + "\n", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Redact personal and business data from a CSV file. "
                    "All processing is local - no data leaves this machine.",
    )
    parser.add_argument("input", help="Path to the input CSV file")
    parser.add_argument(
        "-o", "--output",
        help="Path for the redacted CSV (default: <input>_redacted.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview redaction counts without writing the output file",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_file():
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        output_path = str(input_path.with_stem(input_path.stem + "_redacted"))

    report = process_csv(
        input_path=str(input_path),
        output_path=output_path,
        dry_run=args.dry_run,
    )
    print_report(report)

    if not args.dry_run:
        print(f"Redacted file written to: {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
