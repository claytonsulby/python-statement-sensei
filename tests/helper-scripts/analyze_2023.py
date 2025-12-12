import pdftotext
import fitz
from io import BytesIO
import re

def analyze_2023():
    filename = "2023_statement.pdf"
    print(f"--- Analyzing {filename} ---")
    try:
        doc = fitz.open(f"docs/{filename}")
        pdf_bytes = BytesIO(doc.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)
        
        print("First 1000 characters:")
        print(text[:1000])
        
        # Test the regex
        regex = r"Statement period:\s+(\d{2}/\d{2}/\d{2,4})\s+-\s+(\d{2}/\d{2}/\d{2,4})"
        match = re.search(regex, text)
        if match:
            print(f"\nREGEX MATCHED: {match.groups()}")
        else:
            print("\nREGEX DID NOT MATCH")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_2023()
