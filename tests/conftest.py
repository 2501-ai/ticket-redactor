import csv
import os
import tempfile

import pytest

from ticket_redactor.redactor import create_analyzer, PlaceholderMap


@pytest.fixture(scope="module")
def analyzer():
    """Shared analyzer instance (expensive to create)."""
    return create_analyzer()


@pytest.fixture
def pmap():
    return PlaceholderMap()


def write_csv(rows, path=None, delimiter=","):
    """Helper: write rows to a temp CSV and return the path."""
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=delimiter)
        for row in rows:
            writer.writerow(row)
    return path
