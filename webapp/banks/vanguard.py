import re
import pdftotext
from io import BytesIO
from datetime import datetime
from monopoly.banks.base import BankBase
from monopoly.config import PdfConfig, StatementConfig
from monopoly.constants import EntryType
from monopoly.identifiers import TextIdentifier
from monopoly.statements import Transaction


class VanguardTransactionHistoryPrintBank(BankBase):
    name = "VanguardTransactionHistoryPrintBank"
    
    identifiers = [
        [TextIdentifier("Transaction history")],
        [TextIdentifier("transaction history")],
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

        transactions = []
        
        # Extract year from "Value as of:" line
        # Example: "Value as of: December 12, 2025, 4:00 p.m., Eastern time"
        value_as_of_match = re.search(
            r"Value as of:\s*[A-Za-z]+\s+\d{1,2},\s+(\d{4})",
            text,
            re.IGNORECASE
        )
        year = datetime.now().year
        if value_as_of_match:
            year = int(value_as_of_match.group(1))
        
        lines = text.split('\n')
        
        # Find the header row and determine Type column position
        header_found = False
        header_line_idx = -1
        type_column_start = -1
        type_column_end = -1
        
        for i, line in enumerate(lines):
            if "Date" in line and "Symbol" in line and "Amount" in line:
                header_found = True
                header_line_idx = i
                # Find the position of "Type" in the header
                type_pos = line.find("Type")
                if type_pos >= 0:
                    type_column_start = type_pos
                    # Type column typically ends where "Quantity" starts
                    quantity_pos = line.find("Quantity", type_pos)
                    if quantity_pos > type_pos:
                        type_column_end = quantity_pos
                    else:
                        # Fallback: assume Type column is about 20-30 characters wide
                        type_column_end = type_pos + 30
                break
        
        if not header_found or type_column_start < 0:
            return transactions
        
        # Parse transactions - they span multiple lines
        # Format: Date | Symbol | Name (wraps) | Account (wraps) | Type | Quantity | Price | Fees | Amount
        i = header_line_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Stop if we hit page markers or end
            if "Page" in line or "More account information" in line or "Visit customized" in line:
                break
            
            # Check if line starts with a date (MM/DD/YYYY)
            # Strip first to handle any leading whitespace, then check
            date_match = re.match(r"(\d{1,2}/\d{1,2}/\d{4})", line.strip())
            if date_match:
                date_str = date_match.group(1)
                
                # Extract amount from end of line (look for $X.XX or -$X.XX)
                amount_match = re.search(r"([-+]?\$[\d,]+\.\d{2})\s*$", line)
                if not amount_match:
                    # Amount might be on a continuation line, check next few lines
                    for j in range(i+1, min(i+5, len(lines))):
                        next_line = lines[j].strip()
                        amount_match = re.search(r"([-+]?\$[\d,]+\.\d{2})\s*$", next_line)
                        if amount_match:
                            break
                
                if amount_match:
                    amount_str = amount_match.group(1).replace('$', '').replace(',', '').strip()
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        i += 1
                        continue
                    
                    # Extract Type column by finding the exact phrase boundaries
                    # The Type appears after account info (ends with "—") and before quantity column (starts with "—")
                    desc = "Transaction"  # Default
                    
                    # Find where account info ends (look for "—" before the Type column position)
                    account_end = line.rfind('—', 0, type_column_start)
                    if account_end < 0:
                        # Fallback: look for "Account" or find a reasonable position
                        account_end = line.rfind('Account', 0, type_column_start)
                        if account_end < 0:
                            account_end = type_column_start - 20  # Fallback position
                    
                    # Find the start of Type text (skip whitespace after account end)
                    type_start = account_end + 1
                    while type_start < len(line) and line[type_start] == ' ':
                        type_start += 1
                    
                    # Find the end of Type text (look for "—" which marks the quantity column)
                    # or multiple spaces which indicate column boundary
                    type_end = line.find('—', type_start)
                    if type_end < 0:
                        # Look for pattern of multiple spaces (2+ spaces) which often marks column boundary
                        # But be careful not to break on single spaces within multi-word types
                        space_pattern = re.search(r'\s{3,}', line[type_start:])
                        if space_pattern:
                            type_end = type_start + space_pattern.start()
                        else:
                            # Fallback: use a reasonable width
                            type_end = min(type_start + 30, len(line))
                    
                    # Extract the Type text
                    if type_start < len(line) and type_end > type_start:
                        type_col_text = line[type_start:type_end].strip()
                        
                        # Clean up: remove trailing dashes/extra whitespace and strip numeric noise
                        type_col_text = re.sub(r'\s*—.*$', '', type_col_text)
                        # Keep only letters, spaces, hyphens, and parentheses; drop digits/commas/symbols
                        type_col_text = re.sub(r'[^A-Za-z\s\-\(\)]+', ' ', type_col_text)
                        type_col_text = re.sub(r'\s+', ' ', type_col_text).strip()
                        
                        # If we got a meaningful value, use it
                        if type_col_text:
                            desc = type_col_text
                        else:
                            # Check continuation lines if type wasn't found on main line
                            for j in range(i+1, min(i+4, len(lines))):
                                next_line = lines[j].strip()
                                # If next line doesn't start with a date, it's likely a continuation
                                if not re.match(r'^\d{1,2}/\d{1,2}/\d{4}', next_line):
                                    # Try to extract type from continuation line using same method
                                    cont_account_end = next_line.rfind('—', 0, type_column_start)
                                    if cont_account_end < 0:
                                        cont_account_end = type_column_start - 20
                                    
                                    cont_type_start = cont_account_end + 1
                                    while cont_type_start < len(next_line) and next_line[cont_type_start] == ' ':
                                        cont_type_start += 1
                                    
                                    cont_type_end = next_line.find('—', cont_type_start)
                                    if cont_type_end < 0:
                                        space_pattern = re.search(r'\s{3,}', next_line[cont_type_start:])
                                        if space_pattern:
                                            cont_type_end = cont_type_start + space_pattern.start()
                                        else:
                                            cont_type_end = min(cont_type_start + 30, len(next_line))
                                    
                                    if cont_type_start < len(next_line) and cont_type_end > cont_type_start:
                                        cont_type_text = next_line[cont_type_start:cont_type_end].strip()
                                        cont_type_text = re.sub(r'\s*—.*$', '', cont_type_text)
                                        cont_type_text = re.sub(r'[^A-Za-z\s\-\(\)]+', ' ', cont_type_text)
                                        cont_type_text = re.sub(r'\s+', ' ', cont_type_text).strip()
                                        
                                        # Verify it's not part of account name
                                        if cont_type_text and cont_type_text not in ["Vanguard", "Federal", "Money", "Market", "Fund", "Account", "Brokerage", "Sulby"]:
                                            desc = cont_type_text
                                            break
                                else:
                                    # Hit next transaction, stop looking
                                    break
                    
                    # Determine polarity
                    polarity = None
                    desc_lower = desc.lower()
                    if "dividend" in desc_lower or "interest" in desc_lower:
                        polarity = "CR"
                    elif "reinvestment" in desc_lower:
                        polarity = None  # Reinvestment is typically a debit
                    elif amount < 0:
                        polarity = None
                    else:
                        polarity = "CR"
                    
                    # Parse date
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
                        full_date_str = parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        i += 1
                        continue
                    
                    transactions.append(Transaction(
                        description=desc.strip(),
                        amount=amount,
                        transaction_date=full_date_str,
                        polarity=polarity
                    ))
            
            i += 1
        
        return transactions


class VanguardCustomActivityReportBank(BankBase):
    name = "VanguardCustomActivityReportBank"
    
    identifiers = [
        [TextIdentifier("Vanguard"), TextIdentifier("Settlement date")],
        [TextIdentifier("Custom report created on")],
        [TextIdentifier("Vanguard"), TextIdentifier("Trade date")],
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

        transactions = []
        
        # Extract date range from "settled from" line
        period_match = re.search(
            r"settled from:\s*(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})",
            text,
            re.IGNORECASE
        )
        start_date = None
        end_date = None
        if period_match:
            start_str = period_match.group(1)
            end_str = period_match.group(2)
            try:
                start_date = datetime.strptime(start_str, "%m/%d/%Y")
                end_date = datetime.strptime(end_str, "%m/%d/%Y")
            except ValueError:
                pass
        
        lines = text.split('\n')
        
        # Find the header row
        header_found = False
        header_line_idx = -1
        for i, line in enumerate(lines):
            if "Settlement" in line and "Trade date" in line and "Amount" in line:
                header_found = True
                header_line_idx = i
                break
        
        if not header_found:
            return transactions
        
        # Parse transactions - they span multiple lines
        # Format: Settlement date | Trade date | Symbol | Name (wraps) | Transaction type | Account type | Quantity | Price | Fees | Amount
        i = header_line_idx + 1
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            
            # Stop if we hit page markers or footer
            if "Custom report created on" in line or "Page" in line:
                # Check if it's a continuation header
                if "continued" not in line.lower():
                    i += 1
                    continue
                else:
                    # Skip to next header
                    for j in range(i+1, min(i+10, len(lines))):
                        if "Settlement" in lines[j] and "Trade date" in lines[j]:
                            i = j
                            break
                    i += 1
                    continue
            
            # Check if line starts with a date (MM/DD/YYYY) - this is the settlement date
            date_match = re.match(r"^(\d{1,2}/\d{1,2}/\d{4})", line)
            if date_match:
                settlement_date_str = date_match.group(1)
                
                # Look for trade date (should be right after settlement date)
                trade_date_match = re.search(r"^\d{1,2}/\d{1,2}/\d{4}\s+(\d{1,2}/\d{1,2}/\d{4})", line)
                trade_date_str = settlement_date_str  # Default to settlement date
                if trade_date_match:
                    trade_date_str = trade_date_match.group(1)
                
                # Use trade date as transaction date
                date_str = trade_date_str
                
                # Extract amount from end of line or continuation lines
                amount_match = re.search(r"([-+]?\$[\d,]+\.\d{2})\s*$", line)
                if not amount_match:
                    # Check next few lines for amount
                    for j in range(i+1, min(i+5, len(lines))):
                        next_line = lines[j].strip()
                        amount_match = re.search(r"([-+]?\$[\d,]+\.\d{2})\s*$", next_line)
                        if amount_match:
                            break
                
                if amount_match:
                    amount_str = amount_match.group(1).replace('$', '').replace(',', '').strip()
                    try:
                        amount = float(amount_str)
                    except ValueError:
                        i += 1
                        continue
                    
                    # Skip if amount is 0 or missing
                    if abs(amount) < 0.01:
                        i += 1
                        continue
                    
                    # Extract description from the line
                    # Format: Date Date Symbol Name TransactionType AccountType ...
                    parts = line.split()
                    if len(parts) >= 3:
                        # Symbol is usually 3rd element (after two dates)
                        symbol = parts[2] if parts[2] != "—" else ""
                        
                        # Find transaction type (Transfer, Sweep, Dividend, etc.)
                        desc_parts = []
                        type_found = False
                        for part in parts[3:]:
                            if part in ["Transfer", "Sweep", "Dividend", "Reinvestment", "Buy", "Sell", 
                                       "Corp", "Action", "Stock", "split", "Exchange"]:
                                type_found = True
                            if type_found:
                                if part in ["(incoming)", "(Outgoing)", "(in", "Lieu)", "split", "(Exchange)"]:
                                    desc_parts.append(part)
                                elif part in ["Transfer", "Sweep", "Dividend", "Reinvestment", "Buy", "Sell", 
                                            "Corp", "Action", "Stock", "Exchange"]:
                                    desc_parts.append(part)
                                elif "$" in part or re.match(r"^-?\$", part):
                                    break
                                elif part not in ["—", "-", "CASH", "MARGIN"] and not part.replace('.', '').replace('-', '').isdigit():
                                    # Add name parts
                                    if len(desc_parts) < 5:  # Limit description length
                                        desc_parts.append(part)
                        
                        # Build description
                        if symbol and desc_parts:
                            desc = f"{symbol} - {' '.join(desc_parts)}"
                        elif symbol:
                            desc = symbol
                        elif desc_parts:
                            desc = ' '.join(desc_parts)
                        else:
                            desc = "Transaction"
                    else:
                        desc = "Transaction"
                    
                    # Determine polarity
                    polarity = None
                    desc_lower = desc.lower()
                    
                    # Credit transactions
                    if any(keyword in desc_lower for keyword in ["dividend", "interest", "transfer (incoming)", 
                                                                  "transfer incoming", "sweep in", "deposit"]):
                        polarity = "CR"
                    # Debit transactions
                    elif any(keyword in desc_lower for keyword in ["transfer (outgoing)", "transfer outgoing", 
                                                                    "sweep out", "withdrawal", "fee", "reinvestment"]):
                        polarity = None
                    else:
                        # Default: negative = debit, positive = credit
                        if amount < 0:
                            polarity = None
                        else:
                            polarity = "CR"
                    
                    # Parse date
                    try:
                        parsed_date = datetime.strptime(date_str, "%m/%d/%Y")
                        full_date_str = parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        i += 1
                        continue
                    
                    transactions.append(Transaction(
                        description=desc.strip(),
                        amount=amount,
                        transaction_date=full_date_str,
                        polarity=polarity
                    ))
            
            i += 1
        
        return transactions


class Vanguard401kStatementBank(BankBase):
    name = "Vanguard401kStatementBank"

    identifiers = [
        [TextIdentifier("ACCOUNT SUMMARY"), TextIdentifier("VANGUARD RETIREMENT")],
        [TextIdentifier("Retirement Plans Document"), TextIdentifier("Your Account Summary")],
    ]

    statement_configs = [
        StatementConfig(
            statement_type=EntryType.DEBIT,
            transaction_pattern=re.compile(r"dummy"),
            statement_date_pattern=re.compile(r"dummy"),
            header_pattern=re.compile(r"dummy"),
        )
    ]

    _amount_pattern = re.compile(r"[-+]?\$?[\d,]+\.\d{2}")
    _metrics = (
        ("your contributions", "Employee contributions", "CR"),
        ("employer contributions", "Employer contributions", "CR"),
        ("market gain/loss", "Market gain/loss", None),
    )

    @classmethod
    def extract(cls, document):
        pdf_bytes = BytesIO(document.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)

        lines = [line.rstrip() for line in text.splitlines()]
        statement_date = cls._statement_end_date(text)

        transactions = []
        for keyword, description, default_polarity in cls._metrics:
            amount = cls._metric_amount(lines, keyword)
            if amount is None or abs(amount) < 0.01:
                continue

            polarity = default_polarity if amount > 0 else None
            if polarity is None and amount > 0:
                polarity = "CR"

            transactions.append(Transaction(
                description=description,
                amount=amount,
                transaction_date=statement_date,
                polarity=polarity
            ))

        return transactions

    @classmethod
    def _statement_end_date(cls, text):
        match = re.search(
            r"ACCOUNT SUMMARY:\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})",
            text,
            re.IGNORECASE,
        )
        date_obj = cls._parse_date(match.group(2), "%m/%d/%Y") if match else None

        if not date_obj:
            match = re.search(
                r"account activity from\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})\s+to\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})",
                text,
                re.IGNORECASE,
            )
            if match:
                end_str = re.sub(r"\s+", " ", match.group(2).strip())
                date_obj = cls._parse_date(end_str, "%B %d, %Y")

        if not date_obj:
            date_obj = datetime.now()

        return date_obj.strftime("%Y-%m-%d")

    @staticmethod
    def _parse_date(value, fmt):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            return None

    @classmethod
    def _metric_amount(cls, lines, keyword):
        keyword = keyword.lower()
        for idx, line in enumerate(lines):
            if keyword in line.lower().strip():
                amount = cls._find_amount_near(lines, idx)
                if amount is not None:
                    return amount
        return None

    @classmethod
    def _find_amount_near(cls, lines, idx):
        for offset in range(0, 5):
            pos = idx + offset
            if pos >= len(lines):
                break
            cleaned = lines[pos].replace(" ", "")
            match = cls._amount_pattern.search(cleaned)
            if match:
                return cls._normalize_amount(match.group())
        return None

    @staticmethod
    def _normalize_amount(value):
        cleaned = value.replace("$", "").replace(",", "")
        cleaned = cleaned.replace("−", "-")
        if cleaned.startswith("+"):
            cleaned = cleaned[1:]
        return float(cleaned)
