import sqlite3
import json
import os

# Database path from config.py logic
DB_PATH = os.path.join(os.getcwd(), "data", "ciris_agent.db")

def dump_table(conn, table_name):
    print(f"\n--- Contents of {table_name} ---")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        if not rows:
            print(f"Table {table_name} is empty or does not exist.")
            return

        column_names = [description[0] for description in cursor.description]
        print(f"Columns: {column_names}")

        for i, row in enumerate(rows):
            print(f"\nRow {i+1}:")
            row_dict = dict(zip(column_names, row))
            for col, val in row_dict.items():
                if isinstance(val, str) and ('_json' in col or col.endswith('_text')): # Attempt to pretty print JSON strings
                    try:
                        parsed_json = json.loads(val)
                        print(f"  {col}: {json.dumps(parsed_json, indent=2)}")
                    except json.JSONDecodeError:
                        print(f"  {col}: {val} (not valid JSON)")
                else:
                    print(f"  {col}: {val}")
            print("-" * 20)

    except sqlite3.Error as e:
        print(f"Error reading from {table_name}: {e}")
    finally:
        cursor.close()

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at: {DB_PATH}")
        return

    print(f"Connecting to database at: {DB_PATH}")
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        dump_table(conn, "tasks_table")
        dump_table(conn, "thoughts_table")
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()
