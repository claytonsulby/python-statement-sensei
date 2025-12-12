import pandas as pd
from monopoly.statements import Transaction

# Create a sample transaction
t = Transaction(
    description="Test",
    amount=100.0,
    transaction_date="2023-01-01",
    polarity="CR"
)

# Create DataFrame
df = pd.DataFrame([t])
print("DataFrame columns:", df.columns)
print("DataFrame content:")
print(df)

if "date" in df.columns:
    print("SUCCESS: 'date' column found")
else:
    print("FAILURE: 'date' column NOT found")
