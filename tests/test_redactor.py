"""Tests for ticket_redactor.redactor"""

import csv
from pathlib import Path

import pytest

from ticket_redactor.redactor import (
    PlaceholderMap,
    detect_dialect,
    process_csv,
    redact_cell,
)
from tests.conftest import write_csv


# ---------------------------------------------------------------------------
# PlaceholderMap
# ---------------------------------------------------------------------------

class TestPlaceholderMap:
    def test_deterministic(self, pmap):
        p1 = pmap.get("EMAIL", "alice@test.com")
        p2 = pmap.get("EMAIL", "alice@test.com")
        assert p1 == p2 == "[EMAIL-1]"

    def test_case_insensitive(self, pmap):
        p1 = pmap.get("EMAIL", "Alice@Test.COM")
        p2 = pmap.get("EMAIL", "alice@test.com")
        assert p1 == p2

    def test_different_values_different_placeholders(self, pmap):
        p1 = pmap.get("PERSON", "Alice")
        p2 = pmap.get("PERSON", "Bob")
        assert p1 != p2
        assert p1 == "[PERSON-1]"
        assert p2 == "[PERSON-2]"

    def test_stats(self, pmap):
        pmap.get("EMAIL", "a@b.com")
        pmap.get("EMAIL", "a@b.com")
        pmap.get("EMAIL", "c@d.com")
        assert pmap.stats["EMAIL"] == 3
        assert pmap.unique_counts()["EMAIL"] == 2


# ---------------------------------------------------------------------------
# Cell-level redaction
# ---------------------------------------------------------------------------

class TestRedactCell:
    def test_email(self, analyzer, pmap):
        result = redact_cell("Contact alice@example.com please", analyzer, pmap)
        assert "alice@example.com" not in result
        assert "[EMAIL-" in result

    def test_phone_international(self, analyzer, pmap):
        result = redact_cell("Call +33 6 12 34 56 78", analyzer, pmap)
        assert "12 34 56 78" not in result

    def test_ip_address(self, analyzer, pmap):
        result = redact_cell("Server at 192.168.1.100", analyzer, pmap)
        assert "192.168.1.100" not in result

    def test_credit_card(self, analyzer, pmap):
        result = redact_cell("Card: 4532015112830366", analyzer, pmap)
        assert "4532015112830366" not in result

    def test_iban(self, analyzer, pmap):
        result = redact_cell("IBAN: FR7630006000011234567890189", analyzer, pmap)
        assert "FR7630006000011234567890189" not in result

    def test_mac_address(self, analyzer, pmap):
        result = redact_cell("MAC AA:BB:CC:DD:EE:FF", analyzer, pmap)
        assert "AA:BB:CC:DD:EE:FF" not in result
        assert "[MAC_ADDRESS-" in result

    def test_hostname(self, analyzer, pmap):
        result = redact_cell("Check srv-prod-01.internal", analyzer, pmap)
        assert "srv-prod-01.internal" not in result
        assert "[HOSTNAME-" in result

    def test_person_name(self, analyzer, pmap):
        result = redact_cell("Client John Smith reported an issue", analyzer, pmap)
        assert "John Smith" not in result

    def test_empty_cell(self, analyzer, pmap):
        assert redact_cell("", analyzer, pmap) == ""
        assert redact_cell("   ", analyzer, pmap) == "   "

    def test_no_pii(self, analyzer, pmap):
        text = "Ticket resolved, closing."
        result = redact_cell(text, analyzer, pmap)
        assert result == text

    def test_multiple_pii_in_one_cell(self, analyzer, pmap):
        text = "Email alice@test.com, IP 10.0.0.1, MAC AA:BB:CC:DD:EE:FF"
        result = redact_cell(text, analyzer, pmap)
        assert "alice@test.com" not in result
        assert "10.0.0.1" not in result
        assert "AA:BB:CC:DD:EE:FF" not in result


# ---------------------------------------------------------------------------
# CSV-level processing
# ---------------------------------------------------------------------------

class TestProcessCSV:
    def test_basic_csv(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        write_csv([
            ["name", "email", "note"],
            ["John Smith", "john@example.com", "No issues"],
            ["Jane Doe", "jane@example.com", "Call +1 555-123-4567"],
        ], input_path)

        report = process_csv(input_path, output_path)

        assert Path(output_path).exists()
        assert report["total_rows"] == 2
        assert report["cells_redacted"] > 0

        with open(output_path, encoding="utf-8") as f:
            content = f.read()
        assert "john@example.com" not in content
        assert "jane@example.com" not in content

    def test_original_not_modified(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        rows = [
            ["name", "email"],
            ["Alice", "alice@example.com"],
        ]
        write_csv(rows, input_path)

        with open(input_path, encoding="utf-8") as f:
            original_content = f.read()

        process_csv(input_path, output_path)

        with open(input_path, encoding="utf-8") as f:
            after_content = f.read()
        assert original_content == after_content

    def test_dry_run(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        write_csv([
            ["name", "email"],
            ["Bob", "bob@example.com"],
        ], input_path)

        report = process_csv(input_path, output_path, dry_run=True)

        assert not Path(output_path).exists()
        assert "dry run" in report["output_file"]

    def test_preserves_row_count(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        num_rows = 50
        rows = [["id", "email"]]
        for i in range(num_rows):
            rows.append([str(i), f"user{i}@company.com"])
        write_csv(rows, input_path)

        process_csv(input_path, output_path)

        with open(output_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            output_rows = list(reader)
        # header + data rows
        assert len(output_rows) == num_rows + 1

    def test_utf8_bom(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        with open(input_path, "w", encoding="utf-8-sig") as f:
            f.write("name,email\n")
            f.write("Alice,alice@example.com\n")

        report = process_csv(input_path, output_path)
        assert report["total_rows"] == 1

    def test_semicolon_delimiter(self, tmp_path):
        input_path = str(tmp_path / "input.csv")
        output_path = str(tmp_path / "output.csv")
        write_csv([
            ["name", "email"],
            ["Alice", "alice@example.com"],
        ], input_path, delimiter=";")

        report = process_csv(input_path, output_path)
        assert report["total_rows"] == 1
        assert report["cells_redacted"] > 0


# ---------------------------------------------------------------------------
# Dialect detection
# ---------------------------------------------------------------------------

class TestDetectDialect:
    def test_comma(self, tmp_path):
        path = str(tmp_path / "test.csv")
        write_csv([["a", "b"], ["1", "2"]], path, delimiter=",")
        dialect = detect_dialect(path)
        assert dialect.delimiter == ","

    def test_semicolon(self, tmp_path):
        path = str(tmp_path / "test.csv")
        write_csv([["a", "b"], ["1", "2"]], path, delimiter=";")
        dialect = detect_dialect(path)
        assert dialect.delimiter == ";"
