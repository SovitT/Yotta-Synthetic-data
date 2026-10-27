import sqlite3

conn = sqlite3.connect("journey_pipeline.db")
cursor = conn.cursor()

# Get all table names
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print("=== DATABASE TABLES & ROW COUNTS ===")
for table_name in tables:
    t = table_name[0]
    cursor.execute(f"SELECT COUNT(*) FROM '{t}';")
    count = cursor.fetchone()[0]
    print(f"Table: {t:<20} | Rows: {count}")

conn.close()