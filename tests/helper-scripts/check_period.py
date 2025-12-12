import pdftotext
import fitz
from io import BytesIO
import re
import os

def check_period(filename):
    print(f"--- Checking {filename} ---")
    try:
        doc = fitz.open(f"docs/{filename}")
        pdf_bytes = BytesIO(doc.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)
        
        # Search for "Statement period" or "For the period"
        match_cc = re.search(r"Statement period:.*", text)
        if match_cc:
            print(f"Found CC Period Line: '{match_cc.group(0)}'")
        else:
            print("CC Period Line NOT FOUND")
            
        match_debit = re.search(r"For the period.*", text)
        if match_debit:
            print(f"Found Debit Period Line: '{match_debit.group(0)}'")
        else:
            print("Debit Period Line NOT FOUND")
            
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

if __name__ == "__main__":
    files = [f for f in os.listdir("docs") if f.endswith(".pdf")]
    for f in files:
        check_period(f)
