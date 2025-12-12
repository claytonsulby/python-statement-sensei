import pdftotext
import fitz
from io import BytesIO

def analyze_withdraw():
    filename = "withdraw_statement.pdf"
    print(f"--- Analyzing {filename} ---")
    try:
        doc = fitz.open(f"docs/{filename}")
        pdf_bytes = BytesIO(doc.tobytes())
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)
        
        print(text)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze_withdraw()
