import re

def test_fee_conflict():
    line = "12/01 12/01 ONLINE CREDIT CARD PMT 12/01 XXXX3891 $663.86- ."
    
    fee_pattern = re.compile(r"^\s*(\d{2}/\d{2})\s+(?!\d{2}/\d{2})(.*?)\s+(\$[\d,]+\.\d{2})")
    
    match = fee_pattern.match(line)
    if match:
        print(f"FEE MATCHED: {match.groups()}")
    else:
        print("FEE DID NOT MATCH")

if __name__ == "__main__":
    test_fee_conflict()
