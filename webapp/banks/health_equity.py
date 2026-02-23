import re
from datetime import datetime
from io import BytesIO

import pdftotext

from monopoly.banks.base import BankBase
from monopoly.config import StatementConfig
from monopoly.constants import EntryType
from monopoly.identifiers import TextIdentifier
from monopoly.statements import Transaction


class HealthEquityBank(BankBase):
    name = "HealthEquityBank"

    identifiers = [
        [TextIdentifier("HealthEquity"), TextIdentifier("Health Savings Account")],
        [TextIdentifier("HealthEquity"), TextIdentifier("Deposit or (Withdrawal)")],
    ]

    statement_configs = [
        StatementConfig(
            statement_type=EntryType.DEBIT,
            transaction_pattern=re.compile(r"dummy"),
            statement_date_pattern=re.compile(r"dummy"),
            header_pattern=re.compile(r"dummy"),
        )
    ]

    _date_pattern = re.compile(r"^(\d{2}/\d{2}/\d{4})")

    @classmethod
    def extract(cls, document):
        pdf_bytes = BytesIO(document.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)

        transactions = []
        for raw_line in text.splitlines():
            entry = raw_line.strip(" _\t")
            if not entry:
                continue

            date_match = cls._date_pattern.match(entry)
            if not date_match:
                continue

            columns = re.split(r"\s{2,}", entry)
            if len(columns) < 3:
                continue

            date_str = columns[0].strip()
            description = columns[1].strip()
            amount_str = columns[-2].strip()

            amount = cls._parse_amount(amount_str)
            if amount is None:
                continue

            normalized_date = cls._normalize_date(date_str)
            if not normalized_date:
                continue

            polarity = "CR" if amount > 0 else None
            transactions.append(Transaction(
                description=description,
                amount=amount,
                transaction_date=normalized_date,
                polarity=polarity,
            ))

        return transactions

    @staticmethod
    def _normalize_date(date_str):
        try:
            return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            return None

    @staticmethod
    def _parse_amount(value):
        cleaned = value.strip()
        if not cleaned:
            return None

        negative = False
        if cleaned.startswith("(") and cleaned.endswith(")"):
            negative = True
            cleaned = cleaned[1:-1]

        cleaned = cleaned.replace("$", "").replace(",", "")
        cleaned = cleaned.replace(" ", "")

        if cleaned.startswith("-"):
            negative = True
            cleaned = cleaned[1:]
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]

        try:
            amount = float(cleaned)
        except ValueError:
            return None

        return -amount if negative else amount
