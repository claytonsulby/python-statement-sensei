import pytest
from unittest.mock import MagicMock
from webapp.banks.pnc import PNCBank
# Use real Transaction class if available, or just check attributes
try:
    from monopoly.statements import Transaction
except ImportError:
    # Fallback if running without venv (shouldn't happen with correct command)
    pass

# Mock text content based on the PDF analysis (simulating pdftotext -layout)
SAMPLE_PDF_TEXT = """
Virtual Wallet Spend Statement
PNC Bank
Primary account number:
84-0279-0339
For the period
12/06/2018 to 01/04/2019

Activity Detail
Deposits and Other Additions
There were 3 Deposits and Other
Additions totaling $1,321.02.
Date        Amount      Description
12/10       500.00      Online Transfer From      0000008602210554
12/11       21.02       Direct Deposit - Cashout Venmo XXXXXX9978

Online and Electronic Banking Deductions
There were 5 Online or Electronic
Banking Deductions totaling
$914.35.
Date        Amount      Description
12/06       30.57       Web Pmt Single - Inst Xfer Paypal Grubhubfood
12/10       16.43       Web Pmt Single - Echeck Paypal Statecolleg
"""

def test_pnc_parser():
    # Mock the document to return pages with text
    document = MagicMock()
    page = MagicMock()
    page.extract_text.return_value = SAMPLE_PDF_TEXT
    # Also support iteration for pages
    document.__iter__.return_value = [page]
    
    # Call extract directly
    transactions = PNCBank.extract(document)
    
    # Check transactions
    assert len(transactions) > 0
    
    # Check specific transaction
    # Note: Transaction object has .amount, .description, .date (string YYYY-MM-DD)
    
    t1 = next((t for t in transactions if t.amount == 500.00 and "Online Transfer" in t.description), None)
    assert t1 is not None
    # Date should be 2018-12-10 because statement period starts in 2018
    assert t1.date == "2018-12-10" 
    
    t2 = next((t for t in transactions if t.amount == -30.57), None)
    assert t2 is not None
    assert t2.date == "2018-12-06"
