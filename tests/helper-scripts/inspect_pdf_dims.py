import fitz

pdf_path = "docs/pnc_statement.pdf"
try:
    doc = fitz.open(pdf_path)
    page = doc[0]
    print(f"MediaBox: {page.mediabox}")
    print(f"CropBox: {page.cropbox}")
    print(f"Rect: {page.rect}")
except Exception as e:
    print(f"Error: {e}")
