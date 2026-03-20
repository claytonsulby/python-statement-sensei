"""CLI entry point: parse a single PDF statement and print JSON to stdout.

Usage: python3 cli.py <path-to-pdf>

Output schema:
  {
    "bankName": str,
    "accountMask": str | null,
    "startDate": "YYYY-MM-DD" | null,
    "endDate": "YYYY-MM-DD" | null,
    "startBalance": float | null,
    "endBalance": float | null,
    "transactions": [{ "description": str, "amount": float, "date": "YYYY-MM-DD" }]
  }
"""

import json
import re
import sys
from datetime import date, datetime
from io import BytesIO

import pdftotext
from monopoly.banks import BankDetector, banks
from monopoly.generic import GenericBank
from monopoly.pdf import PdfDocument, PdfParser
from monopoly.pipeline import Pipeline
from pydantic import SecretStr

from webapp.banks.health_equity import HealthEquityBank
from webapp.banks.pnc import PNCDebitBank, PNCCreditCardBank
from webapp.banks.vanguard import (
    Vanguard401kStatementBank,
    VanguardCustomActivityReportBank,
    VanguardTransactionHistoryPrintBank,
)

banks.append(PNCDebitBank)
banks.append(PNCCreditCardBank)
banks.append(VanguardTransactionHistoryPrintBank)
banks.append(VanguardCustomActivityReportBank)
banks.append(Vanguard401kStatementBank)
banks.append(HealthEquityBank)

CUSTOM_BANKS = {
    "PNCDebitBank",
    "PNCCreditCardBank",
    "VanguardTransactionHistoryPrintBank",
    "VanguardCustomActivityReportBank",
    "Vanguard401kStatementBank",
    "HealthEquityBank",
}


def extract_text(document: PdfDocument) -> str:
    pdf = pdftotext.PDF(BytesIO(document.tobytes()), physical=True)
    return "\n".join(pdf)


def extract_pnc_debit_account_mask(text: str) -> str | None:
    """Extract last 4 digits of account number from PNC debit statement (e.g. XX-XXXX-0339 → '0339')."""
    m = re.search(r"[Aa]ccount\s+number:\s+[X\-]*(\d{4})", text)
    return m.group(1) if m else None


def extract_pnc_credit_account_mask(text: str) -> str | None:
    """Extract last 4 digits from PNC credit statement (e.g. 'Account number ending in ... 1114' → '1114')."""
    m = re.search(r"[Aa]ccount\s+number\s+ending\s+in\s+[.\s]*(\d+)", text)
    return m.group(1) if m else None


def extract_pnc_debit_metadata(text: str) -> dict:
    """Extract period dates and balances from PNC Virtual Wallet statement text."""
    start_date = end_date = start_balance = end_balance = None

    period = re.search(r"For the period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text)
    if period:
        start_date = datetime.strptime(period.group(1), "%m/%d/%Y").date().isoformat()
        end_date = datetime.strptime(period.group(2), "%m/%d/%Y").date().isoformat()

    # Balance Summary section: "Beginning ... Ending\nbalance ... balance\n<num> ... <num>"
    balance = re.search(
        r"Balance Summary.*?(\d[\d,]*\.\d{2})\s+\d[\d,]*\.\d{2}\s+\d[\d,]*\.\d{2}\s+(\d[\d,]*\.\d{2})",
        text,
        re.DOTALL,
    )
    if balance:
        start_balance = float(balance.group(1).replace(",", ""))
        end_balance = float(balance.group(2).replace(",", ""))

    return {"startDate": start_date, "endDate": end_date, "startBalance": start_balance, "endBalance": end_balance}


def extract_pnc_credit_metadata(text: str) -> dict:
    """Extract period dates and balances from PNC credit card statement text."""
    start_date = end_date = start_balance = end_balance = None

    period = re.search(r"Statement period\s*:\s+(\d{2}/\d{2}/\d{2,4})\s+-\s+(\d{2}/\d{2}/\d{2,4})", text)
    if period:
        s, e = period.group(1), period.group(2)
        s_fmt = "%m/%d/%Y" if len(s.split("/")[2]) == 4 else "%m/%d/%y"
        e_fmt = "%m/%d/%Y" if len(e.split("/")[2]) == 4 else "%m/%d/%y"
        start_date = datetime.strptime(s, s_fmt).date().isoformat()
        end_date = datetime.strptime(e, e_fmt).date().isoformat()

    prev = re.search(r"Previous balance\s+\$([\d,]+\.\d{2})", text)
    if prev:
        start_balance = float(prev.group(1).replace(",", ""))

    new_balances = re.findall(r"New balance\s+\$([\d,]+\.\d{2})", text)
    if new_balances:
        end_balance = float(new_balances[-1].replace(",", ""))

    return {"startDate": start_date, "endDate": end_date, "startBalance": start_balance, "endBalance": end_balance}


def extract_healthequity_metadata(text: str) -> dict:
    """Extract period dates, balances and account mask from HealthEquity HSA statement."""
    start_date = end_date = start_balance = end_balance = account_mask = None

    # "Period: 03/01/25 through 03/31/25"  (2-digit year)
    period = re.search(r"Period:\s+(\d{2}/\d{2}/\d{2})\s+through\s+(\d{2}/\d{2}/\d{2})", text)
    if period:
        start_date = datetime.strptime(period.group(1), "%m/%d/%y").date().isoformat()
        end_date = datetime.strptime(period.group(2), "%m/%d/%y").date().isoformat()

    # "Account Number: 23171473"
    acct = re.search(r"Account Number:\s*(\d+)", text)
    if acct:
        account_mask = acct.group(1)[-4:]  # last 4 digits

    # Beginning Balance from transaction table
    begin = re.search(r"Beginning Balance\s+\$\s*([\d,]+\.\d{2})", text)
    if begin:
        start_balance = float(begin.group(1).replace(",", ""))

    # Ending balance: last dollar amount on the last transaction line
    all_balances = re.findall(r"\d{2}/\d{2}/\d{4}.*?([\d,]+\.\d{2})\s*$", text, re.MULTILINE)
    if all_balances:
        end_balance = float(all_balances[-1].replace(",", ""))

    return {"startDate": start_date, "endDate": end_date, "startBalance": start_balance, "endBalance": end_balance, "accountMask": account_mask}


def extract_vanguard_401k_metadata(text: str) -> dict:
    """Extract period dates and balances from Vanguard 401k statement."""
    start_date = end_date = start_balance = end_balance = None

    # Newer format: "ACCOUNT SUMMARY: 04/01/2024 - 06/30/2024"
    m = re.search(r"ACCOUNT SUMMARY:\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if m:
        start_date = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
        end_date = datetime.strptime(m.group(2), "%m/%d/%Y").date().isoformat()
    else:
        # Older format: "account activity from December 01, 2021 to December 31, 2021"
        m = re.search(r"account activity from\s+([A-Za-z]+ \d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+ \d{1,2},\s*\d{4})", text, re.IGNORECASE)
        if m:
            s = re.sub(r"\s+", " ", m.group(1).strip())
            e = re.sub(r"\s+", " ", m.group(2).strip())
            try:
                start_date = datetime.strptime(s, "%B %d, %Y").date().isoformat()
                end_date = datetime.strptime(e, "%B %d, %Y").date().isoformat()
            except ValueError:
                pass

    # Beginning and ending balance
    begin = re.search(r"Beginning balance\s+\$([\d,]+\.\d{2})", text)
    if begin:
        start_balance = float(begin.group(1).replace(",", ""))
    ending = re.search(r"Ending balance\s+\$([\d,]+\.\d{2})", text)
    if ending:
        end_balance = float(ending.group(1).replace(",", ""))

    return {"startDate": start_date, "endDate": end_date, "startBalance": start_balance, "endBalance": end_balance, "accountMask": None}


def extract_vanguard_activity_report_metadata(text: str) -> dict:
    """Extract date range from Vanguard Custom Activity Report."""
    start_date = end_date = None

    m = re.search(r"settled from:\s*(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})", text, re.IGNORECASE)
    if m:
        start_date = datetime.strptime(m.group(1), "%m/%d/%Y").date().isoformat()
        end_date = datetime.strptime(m.group(2), "%m/%d/%Y").date().isoformat()

    return {"startDate": start_date, "endDate": end_date, "startBalance": None, "endBalance": None, "accountMask": None}


def extract_vanguard_transaction_history_metadata(text: str) -> dict:
    """Extract date range from Vanguard Transaction History Printed."""
    # Use the "Value as of: Month D, YYYY" date as the end date
    m = re.search(r"Value as of:\s*([A-Za-z]+ \d{1,2},\s*\d{4})", text, re.IGNORECASE)
    end_date = None
    if m:
        try:
            end_date = datetime.strptime(re.sub(r"\s+", " ", m.group(1).strip()), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass

    # Derive start date from the earliest transaction date in the text
    dates = re.findall(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", text)
    start_date = None
    if dates:
        parsed = []
        for d in dates:
            try:
                parsed.append(datetime.strptime(d, "%m/%d/%Y").date())
            except ValueError:
                pass
        if parsed:
            start_date = min(parsed).isoformat()

    return {"startDate": start_date, "endDate": end_date, "startBalance": None, "endBalance": None, "accountMask": None}


def extract_metadata(document: PdfDocument, bank_name: str) -> dict:
    """Extract statement-level metadata (dates, balances, account mask) from the PDF text."""
    text = extract_text(document)
    if bank_name == "PNCDebitBank":
        return {**extract_pnc_debit_metadata(text), "accountMask": extract_pnc_debit_account_mask(text)}
    if bank_name == "PNCCreditCardBank":
        return {**extract_pnc_credit_metadata(text), "accountMask": extract_pnc_credit_account_mask(text)}
    if bank_name == "HealthEquityBank":
        return extract_healthequity_metadata(text)
    if bank_name == "Vanguard401kStatementBank":
        return extract_vanguard_401k_metadata(text)
    if bank_name == "VanguardCustomActivityReportBank":
        return extract_vanguard_activity_report_metadata(text)
    if bank_name == "VanguardTransactionHistoryPrintBank":
        return extract_vanguard_transaction_history_metadata(text)
    return {"startDate": None, "endDate": None, "startBalance": None, "endBalance": None, "accountMask": None}


def parse(pdf_path: str) -> dict:
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    document = PdfDocument(file_bytes=file_bytes)
    analyzer = BankDetector(document)
    bank = analyzer.detect_bank(banks) or GenericBank
    parser = PdfParser(bank, document)
    bank_name = bank.__name__

    if bank_name in CUSTOM_BANKS:
        transactions = bank.extract(document)
    else:
        pipeline = Pipeline(parser, passwords=[SecretStr("")])
        statement = pipeline.extract(safety_check=False)
        transactions = pipeline.transform(statement)

    def fmt_date(d) -> str:
        if isinstance(d, date):
            return d.isoformat()
        return str(d)

    metadata = extract_metadata(document, bank_name)

    return {
        "bankName": bank_name,
        **metadata,
        "transactions": [
            {
                "description": t.description,
                "amount": float(t.amount),
                "date": fmt_date(t.date),
            }
            for t in transactions
        ],
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 cli.py <path-to-pdf>", file=sys.stderr)
        sys.exit(1)

    result = parse(sys.argv[1])
    print(json.dumps(result))
