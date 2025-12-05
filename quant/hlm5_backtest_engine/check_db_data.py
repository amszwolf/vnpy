import sqlite3
import pandas as pd

conn = sqlite3.connect('trading_signals.db')
cursor = conn.cursor()

query = "SELECT ticker, MIN(datetime), MAX(datetime), COUNT(*) FROM trading_data GROUP BY ticker"
cursor.execute(query)

print("\n" + "="*80)
print("Database Available Data")
print("="*80)
print(f"{'Ticker':<15} | {'Start Date':<19} | {'End Date':<19} | {'Records':>10}")
print("-"*80)

for row in cursor.fetchall():
    print(f"{row[0]:<15} | {row[1]:<19} | {row[2]:<19} | {row[3]:>10,}")

conn.close()

