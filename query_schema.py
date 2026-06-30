import sqlite3

conn = sqlite3.connect('D:/stock_app/stock_app/stock_warehouse.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cursor.fetchall()]
print("Tables:", tables)

# Get schema for each table
for table in tables:
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cursor.fetchone()
    if row:
        print(f"\n--- {table} ---")
        print(row[0])

conn.close()
