from webapp.banks.pnc import PNCCreditCardBank
from monopoly.statements import Transaction
import re

def reproduce_regression():
    # Mock content with the problematic line
    content = """
    12/01 12/01 ONLINE CREDIT CARD PMT 12/01 XXXX3891 $663.86- .
    """
    
    print(f"Testing content:\n{content}")
    
    # Regex from the file
    cc_pattern = re.compile(r"^\s*(\d{2}/\d{2})\s+(\d{2}/\d{2})\s+(.*?)\s+(-?\$[\d,]+\.\d{2})(.*)")
    
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = cc_pattern.match(line)
        if match:
            print(f"MATCHED line: '{line}'")
            trans_date_str, post_date_str, desc, amount_part, remainder = match.groups()
            print(f"Amount Part: '{amount_part}'")
            print(f"Remainder: '{remainder}'")
            
            full_amount_str = amount_part + remainder
            is_negative = '-' in full_amount_str
            print(f"Is Negative: {is_negative}")
            
            clean_amount_str = amount_part.replace('$', '').replace(',', '').replace('-', '')
            amount = float(clean_amount_str)
            
            polarity = None
            if is_negative:
                amount = abs(amount)
                polarity = "CR"
            else:
                amount = -abs(amount)
                polarity = None
                
            print(f"Calculated Amount: {amount}")
            print(f"Calculated Polarity: {polarity}")
            
            # Create Transaction
            t = Transaction(
                description=desc,
                amount=amount,
                transaction_date="2021-12-01",
                polarity=polarity
            )
            print(f"Final Transaction Amount: {t.amount}")

if __name__ == "__main__":
    reproduce_regression()
