import re
import pdftotext
from io import BytesIO
from datetime import datetime
from monopoly.banks.base import BankBase
from monopoly.config import PdfConfig, StatementConfig
from monopoly.constants import EntryType
from monopoly.identifiers import TextIdentifier
from monopoly.statements import Transaction

class PNCDebitBank(BankBase):
    name = "PNCDebitBank"
    
    identifiers = [
        [TextIdentifier("Virtual Wallet Spend Statement")],
        [TextIdentifier("Virtual Wallet Student Spend Statement")],
        [TextIdentifier("Virtual Wallet Growth Statement")],
        [TextIdentifier("Virtual Wallet Student Growth Statement")],
        [TextIdentifier("Virtual Wallet Reserve Statement")],
        [TextIdentifier("Virtual Wallet Student Reserve Statement")],
    ]
    
    # Dummy config
    statement_configs = [
        StatementConfig(
            statement_type=EntryType.DEBIT,
            transaction_pattern=re.compile(r"dummy"),
            statement_date_pattern=re.compile(r"dummy"),
            header_pattern=re.compile(r"dummy"),
        )
    ]

    @staticmethod
    def extract(document):
        # Use pdftotext to preserve physical layout
        pdf_bytes = BytesIO(document.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)

        # Extract period to determine year
        period_match = re.search(r"For the period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text)
        start_date = None
        end_date = None
        if period_match:
            start_date = datetime.strptime(period_match.group(1), "%m/%d/%Y")
            end_date = datetime.strptime(period_match.group(2), "%m/%d/%Y")

        transactions = []
        
        # Sections to look for
        sections = [
            "Deposits and Other Additions",
            "Online and Electronic Banking Deductions",
            "Checks and other deductions",
            "ATM and Debit Card Deductions",
            "Banking/Debit Card Withdrawals and Purchases",
            "Other Deductions"
        ]
        
        lines = text.split('\n')
        current_section = None
        
        # Regex for transaction line: Date Amount Description
        # 12/10       500.00      Online Transfer...
        # Added \s* at start to handle indentation
        # Updated to handle .01 amounts (no leading zero)
        tx_pattern = re.compile(r"^\s*(\d{2}/\d{2})\s+([0-9,]*\.\d{2})\s+(.*)$")

        for line in lines:
            line = line.strip()
            
            # Check for section headers
            is_section_header = False
            for section in sections:
                if section in line:
                    current_section = section
                    is_section_header = True
                    break
            
            if is_section_header:
                continue
                
            # Stop if we hit "Daily Balance Detail" or other summary sections
            if "Daily Balance Detail" in line or "Balance Summary" in line:
                current_section = None
                continue

            if current_section:
                match = tx_pattern.match(line)
                if match:
                    date_str, amount_str, desc = match.groups()
                    
                    # Parse amount
                    amount = float(amount_str.replace(',', ''))
                    
                    # Determine polarity
                    polarity = None
                    if "Deposits" in current_section or "Additions" in current_section:
                        polarity = "CR" # Positive
                    else:
                        polarity = None # Negative (default behavior of Transaction with auto_polarity=True)
                    
                    # Determine year
                    if start_date:
                        tx_month = int(date_str.split('/')[0])
                        if tx_month == start_date.month:
                            year = start_date.year
                        elif end_date and tx_month == end_date.month:
                            year = end_date.year
                        else:
                            if tx_month >= start_date.month:
                                year = start_date.year
                            else:
                                year = start_date.year + 1
                    else:
                        year = datetime.now().year
                    
                    full_date_str = f"{year}-{date_str.replace('/', '-')}"
                    
                    transactions.append(Transaction(
                        description=desc,
                        amount=amount,
                        transaction_date=full_date_str,
                        polarity=polarity
                    ))

        return transactions


class PNCCreditCardBank(BankBase):
    name = "PNCCreditCardBank"
    
    identifiers = [
        [TextIdentifier("PNC Bank"), TextIdentifier("Account number ending in")],
        [TextIdentifier("Statement period:"), TextIdentifier("Account number ending in")]
    ]
    
    # Dummy config
    statement_configs = [
        StatementConfig(
            statement_type=EntryType.CREDIT,
            transaction_pattern=re.compile(r"dummy"),
            statement_date_pattern=re.compile(r"dummy"),
            header_pattern=re.compile(r"dummy"),
        )
    ]

    @staticmethod
    def extract(document):
        # Use pdftotext to preserve physical layout
        pdf_bytes = BytesIO(document.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)

        transactions = []
        
        # Extract period: "Statement period: 07/31/21 - 08/30/21" or "Statement period : 12/31/22 - 01/30/23"
        period_match = re.search(r"Statement period\s*:\s+(\d{2}/\d{2}/\d{2,4})\s+-\s+(\d{2}/\d{2}/\d{2,4})", text)
        start_date = None
        end_date = None
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            
            # Handle 2-digit or 4-digit year
            start_fmt = "%m/%d/%Y" if len(start_str.split('/')[2]) == 4 else "%m/%d/%y"
            end_fmt = "%m/%d/%Y" if len(end_str.split('/')[2]) == 4 else "%m/%d/%y"
            
            start_date = datetime.strptime(start_str, start_fmt)
            end_date = datetime.strptime(end_str, end_fmt)
        
        # Updated to handle trailing minus: $2000.00- or $663.86 -
        # Capture amount core, then capture everything else as remainder to check for minus
        cc_pattern = re.compile(r"^\s*(\d{2}/\d{2})\s+(\d{2}/\d{2})\s+(.*?)\s+(-?\$[\d,]+\.\d{2})(.*)")
        
        # Pattern for Fees: Date Description Amount (Single date at start)
        # 01/20 *FINANCE CHARGE* TRANSACTION FEE *** $0.54
        fee_pattern = re.compile(r"^\s*(\d{2}/\d{2})\s+(?!\d{2}/\d{2})(.*?)\s+(\$[\d,]+\.\d{2})")
        
        # Pattern for Interest: = Total interest charged... $24.46
        interest_pattern = re.compile(r"^\s*=\s+Total interest charged.*?\s+(\$[\d,]+\.\d{2})")
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            match = cc_pattern.match(line)
            
            # If line matches transaction pattern, process it regardless of other content
            if not match:
                # Only skip headers/footers/summary lines if they are NOT transactions
                if "Previous balance" in line or "Current balance" in line or "Total fees" in line:
                    # Check for Interest before skipping "Total fees" (wait, "Total fees charged in 2018" is summary)
                    # But "Total interest charged in this statement period" is what we want.
                    # Let's check interest pattern FIRST.
                    pass
            
            if match:
                trans_date_str, post_date_str, desc, amount_part, remainder = match.groups()
                
                # Check for negative sign (leading or trailing in remainder)
                # Check for various dash characters: Hyphen, En-dash, Em-dash, Minus Sign
                full_amount_str = amount_part + remainder
                is_negative = any(char in full_amount_str for char in ['-', '–', '—', '−'])
                
                clean_amount_str = amount_part.replace('$', '').replace(',', '').replace('-', '')
                amount = float(clean_amount_str)
                
                # Polarity logic:
                # Statement Positive (Purchase) -> CSV Negative (Spending)
                # Statement Negative (Payment/Credit) -> CSV Positive (Income/Transfer)
                
                polarity = None
                if is_negative:
                    # Payment/Credit: $2000- or -$2000
                    # We want this to be POSITIVE in CSV
                    amount = abs(amount)
                    polarity = "CR" # Explicitly mark as Credit to prevent Transaction from flipping it
                else:
                    # Purchase: $36.45
                    # We want this to be NEGATIVE in CSV
                    amount = -abs(amount)
                    polarity = None # Default is Debit (Negative)
                
                # Determine year
                if start_date:
                    tx_month = int(trans_date_str.split('/')[0])
                    if tx_month == start_date.month:
                        year = start_date.year
                    elif end_date and tx_month == end_date.month:
                        year = end_date.year
                    else:
                        if tx_month >= start_date.month:
                            year = start_date.year
                        else:
                            year = start_date.year + 1
                else:
                    year = datetime.now().year
                    
                full_date_str = f"{year}-{trans_date_str.replace('/', '-')}"
                
                t = Transaction(
                    description=desc,
                    amount=amount,
                    transaction_date=full_date_str,
                    polarity=polarity # Calculated above
                )
                
                transactions.append(t)
                continue

            # Check for Interest
            interest_match = interest_pattern.match(line)
            if interest_match:
                amount_str = interest_match.group(1)
                amount = -abs(float(amount_str.replace('$', '').replace(',', '')))
                
                if abs(amount) < 0.01:
                    continue
                
                # Use end_date or start_date
                date_val = end_date if end_date else datetime.now()
                full_date_str = date_val.strftime("%Y-%m-%d")
                
                transactions.append(Transaction(
                    description="Total Interest Charged",
                    amount=amount,
                    transaction_date=full_date_str,
                    polarity=None
                ))
                continue

            # Check for Fees
            fee_match = fee_pattern.match(line)
            if fee_match:
                trans_date_str, desc, amount_str = fee_match.groups()
                amount = -abs(float(amount_str.replace('$', '').replace(',', '')))
                
                # Determine year (same logic as transactions)
                if start_date:
                    tx_month = int(trans_date_str.split('/')[0])
                    if tx_month == start_date.month:
                        year = start_date.year
                    elif end_date and tx_month == end_date.month:
                        year = end_date.year
                    else:
                        if tx_month >= start_date.month:
                            year = start_date.year
                        else:
                            year = start_date.year + 1
                else:
                    year = datetime.now().year
                
                full_date_str = f"{year}-{trans_date_str.replace('/', '-')}"
                
                transactions.append(Transaction(
                    description=desc,
                    amount=amount,
                    transaction_date=full_date_str,
                    polarity=None
                ))
                continue
            
            # Skip headers/footers/summary lines (Moved to end to allow Interest/Fees checks)
            if "Previous balance" in line or "Current balance" in line or "Total fees" in line:
                 continue

        return transactions
