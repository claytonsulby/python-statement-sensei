import pdftotext
import fitz
from io import BytesIO
from webapp.banks.pnc import PNCDebitBank, PNCCreditCardBank
import pandas as pd

def analyze_error_statement():
    filename = "pnc_error_statement_september_2019.pdf"
    print(f"--- Analyzing {filename} ---")
    try:
        with open(f"docs/{filename}", "rb") as f:
            content = f.read()
            
        doc = fitz.open(f"docs/{filename}")
        pdf_bytes = BytesIO(doc.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)
        
        print("--- PDFTOTEXT CONTENT ---")
        print(text[:1000]) # Just print start
        print("--- END PDFTOTEXT CONTENT ---")
        
        print("\n--- FITZ TEXT CONTENT ---")
        print(doc.get_text("text"))
        print("\n--- FITZ LAYOUT CONTENT ---")
        print(doc.get_text("layout")[:2000]) # First 2000 chars
        
        print("\n--- Testing PNCDebitBank extraction ---")
        try:
            transactions = PNCDebitBank.extract(doc)
            print(f"Found {len(transactions)} transactions.")
            total = sum(t.amount for t in transactions)
            print(f"Total Amount: {total}")
            
            if transactions:
                t = transactions[0]
                # Check attributes
                # print(f"Attributes: {dir(t)}") 
                # Assuming 'date' is the correct attribute based on previous runs or monopoly docs 
                # But let's check both
                
            for t in transactions:
                print(f"{t.date} : {t.amount} : {t.description} : Polarity={t.polarity}")
        except Exception as e:
            print(f"PNCDebitBank Error: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_error_statement()
