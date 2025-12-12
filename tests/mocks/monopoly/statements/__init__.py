class Transaction:
    def __init__(self, date, amount, description):
        self.date = date
        self.amount = amount
        self.description = description

class Statement:
    def __init__(self, transactions, config):
        self.transactions = transactions
        self.config = config
