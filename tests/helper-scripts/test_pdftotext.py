import pdftotext
import fitz
from io import BytesIO

def test_pdftotext():
    pdf_path = "docs/pnc_statement.pdf"
    try:
        # Load PDF bytes using fitz (simulating how we get it from PdfDocument)
        doc = fitz.open(pdf_path)
        pdf_bytes = BytesIO(doc.tobytes())
        
        # Use pdftotext
        pdf = pdftotext.PDF(pdf_bytes, physical=True)
        text = "\n".join(pdf)
        
        print("--- PDFTOTEXT OUTPUT ---")
        print(text)
        print("--- END OUTPUT ---")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pdftotext()
