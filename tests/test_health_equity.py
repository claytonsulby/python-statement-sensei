from pathlib import Path

import pytest

from webapp.banks.health_equity import HealthEquityBank


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
        / "health-equity"
        / "health-equity-statement.pdf"
    )
    return DummyDocument(sample_path.read_bytes())


def test_health_equity_statement_transactions():
    document = _load_sample_document()
    transactions = HealthEquityBank.extract(document)

    assert len(transactions) >= 8

    contributions = [tx for tx in transactions if "Employee Contribution" in tx.description]
    assert len(contributions) == 2
    for tx in contributions:
        assert tx.transaction_date == "2025-11-07" or tx.transaction_date == "2025-11-21"
        assert pytest.approx(tx.amount, rel=1e-4) == 66.54

    investments = [tx for tx in transactions if tx.description.startswith("Investment:")]
    assert {tx.description for tx in investments} == {"Investment: VIIIX", "Investment: VTPSX", "Investment: VSMAX"}
    assert all(tx.amount < 0 for tx in investments)
    assert any(pytest.approx(tx.amount, rel=1e-4) == -33.27 for tx in investments if "VIIIX" in tx.description)
```}