class Bank:
    statement_type = "Generic"
    pdf_config = None
    validation_config = None

    def __init__(self, document):
        self.document = document

    def validate(self, document):
        return True

    def extract(self, document):
        # Mock extraction logic or return a mock statement
        pass

banks = []
BankDetector = None
