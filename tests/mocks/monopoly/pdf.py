class PdfConfig:
    def __init__(self, page_bbox=None):
        self.page_bbox = page_bbox

class ValidationConfig:
    def __init__(self, required_columns=None, date_format=None):
        self.required_columns = required_columns
        self.date_format = date_format

class PdfDocument:
    def __init__(self, file_bytes=None):
        self.file_bytes = file_bytes
        self.pages = []

    def __iter__(self):
        return iter(self.pages)

class MissingOCRError(Exception):
    pass

class PdfParser:
    def __init__(self, bank, document):
        self.bank = bank
        self.document = document
