import fitz
import re
from datetime import datetime
from webapp.banks.pnc import PNCBank

# Mocking Transaction class if needed, or importing it
# But PNCBank imports it from monopoly.statements
# We need to make sure we can run this script with the venv

def test_extraction():
    pdf_path = "docs/pnc_statement.pdf"
    try:
        doc = fitz.open(pdf_path)
        print(f"Opened {pdf_path}")
        
        # Test extraction
        transactions = PNCBank.extract(doc)
        print(f"Extracted {len(transactions)} transactions")
        for t in transactions:
            print(t)
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_extraction()
