from pathlib import Path

import pytest

from webapp.banks.vanguard import Vanguard401kStatementBank


class DummyDocument:
    def __init__(self, data: bytes):
        self._data = data

    def tobytes(self) -> bytes:
        return self._data


def _load_sample_document() -> DummyDocument:
    sample_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "examples"
        / "vanguard-401k"
        / "Retirement Plans Document 21-12.pdf"
    )
    return DummyDocument(sample_path.read_bytes())


def _transaction_date(tx) -> str | None:
    return getattr(tx, "transaction_date", getattr(tx, "date", None))


def test_vanguard_401k_contributions_are_parsed():
    document = _load_sample_document()
    transactions = Vanguard401kStatementBank.extract(document)

    assert transactions, "No transactions parsed from 401k statement"

    amounts = {tx.description: tx.amount for tx in transactions}

    assert pytest.approx(amounts["Employee contributions"], rel=1e-4) == 4560.76
    assert pytest.approx(amounts["Employer contributions"], rel=1e-4) == 8300.56

    employee_tx = next(tx for tx in transactions if tx.description == "Employee contributions")
    assert _transaction_date(employee_tx) == "2022-12-31"

    employer_tx = next(tx for tx in transactions if tx.description == "Employer contributions")
    assert _transaction_date(employer_tx) == "2022-12-31"
