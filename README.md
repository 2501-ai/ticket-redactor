# Ticket Redactor

Redact personal and business data from CSV files containing client
ticket data. All processing happens locally — no data leaves your machine.

## What gets redacted

- Personal names
- Email addresses
- Phone numbers (international formats)
- Physical addresses and locations
- Organization / company names
- IP addresses
- Hostnames (server names like `srv-prod-01.internal`)
- MAC addresses
- Credit card numbers
- IBAN codes
- US Social Security Numbers
- URLs

The tool generates a **new** redacted CSV file. The original file is never
modified. A redaction report is printed showing what was found.

Same values get the same placeholder (e.g. `[PERSON-1]`) so you can still
see patterns across rows without knowing the actual identity.

## Quick start

Requires Python 3.10+ (works on Windows, macOS, and Linux).

```bash
git clone https://github.com/YOUR_ORG/ticket-redactor.git
cd ticket-redactor
pip install .
```

The required spaCy language model (~500 MB) is downloaded automatically on
first run.

## Usage

```bash
ticket-redactor tickets.csv                   # → tickets_redacted.csv
ticket-redactor tickets.csv -o clean.csv      # custom output path
ticket-redactor tickets.csv --dry-run         # preview without writing
```

## Notes

- **Encoding:** Reads UTF-8 (with or without BOM). Outputs UTF-8.
- **CSV dialect:** Auto-detected (comma, semicolon, tab, etc.)
- **Performance:** ~1000 rows/sec on a modern laptop.
- The tool intentionally errs on the side of over-redaction. It is
  better to redact something that looks like PII than to miss actual PII.

## Development

```bash
pip install -e ".[dev]"
pytest
```
