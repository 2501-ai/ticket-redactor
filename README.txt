CSV PII Redactor
================

Redacts personal and business data from CSV files containing client
ticket data. All processing happens locally - no data leaves your machine.

What gets redacted:
  - Personal names
  - Email addresses
  - Phone numbers (international formats)
  - Physical addresses and locations
  - Organization / company names
  - IP addresses
  - Hostnames (server names like srv-prod-01.internal)
  - MAC addresses
  - Credit card numbers
  - IBAN codes
  - US Social Security Numbers
  - URLs

The tool generates a NEW redacted CSV file. The original file is never
modified. A redaction report is always printed showing what was found.

Same values get the same placeholder (e.g. [PERSON-1]) so you can still
see patterns across rows without knowing the actual identity.


Requirements
------------

  Python 3.9 or later (tested on 3.9, 3.10, 3.11, 3.12, 3.13)

  Install dependencies (one-time):

    pip install -r requirements.txt
    python -m spacy download en_core_web_lg


Quick start
-----------

  1. Install dependencies (see above)

  2. Run:

     python redact_csv.py your_tickets.csv

     This creates your_tickets_redacted.csv in the same directory.

  3. Check the report printed to the console for a summary of what
     was redacted.


Options
-------

  python redact_csv.py input.csv                   Default output: input_redacted.csv
  python redact_csv.py input.csv -o output.csv     Custom output path
  python redact_csv.py input.csv --dry-run         Show report without writing output


Running tests
-------------

  pip install pytest
  pytest test_redact.py -v


Notes
-----

  - Encoding: Reads UTF-8 (with or without BOM). Outputs UTF-8.
  - CSV dialect: Auto-detected (comma, semicolon, tab, etc.)
  - Performance: ~1000 rows/sec on a modern laptop. A 5000-row file
    takes about 5 seconds.
  - The tool intentionally errs on the side of over-redaction. It is
    better to redact a ticket ID that looks like a name than to miss
    an actual name.
