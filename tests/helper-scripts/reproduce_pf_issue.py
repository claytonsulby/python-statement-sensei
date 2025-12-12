import pandas as pd
from monopoly.statements import Transaction
from webapp.models import ProcessedFile, TransactionMetadata

# Create a sample transaction
t = Transaction(
    description="Test",
    amount=100.0,
    transaction_date="2023-01-01",
    polarity="CR"
)

# Create ProcessedFile
pf = ProcessedFile(
    transactions=[t],
    metadata=TransactionMetadata(bank_name="TestBank")
)

# Create DataFrame
df = pd.DataFrame(pf)
print("DataFrame columns:", df.columns)
print("DataFrame content:")
print(df)

if "date" in df.columns:
    print("SUCCESS: 'date' column found")
else:
    print("FAILURE: 'date' column NOT found")
