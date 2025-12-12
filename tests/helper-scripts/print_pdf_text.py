import fitz
from webapp.banks.pnc import PNCBank

def print_pdf_text():
    pdf_path = "docs/pnc_statement.pdf"
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text = page.get_text()
            print("--- PAGE START ---")
            print(text)
            print("--- PAGE END ---")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print_pdf_text()
