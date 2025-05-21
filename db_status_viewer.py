import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ciris_engine", "data", "ciris_engine.db")

def print_table_data(table_name, conn, order_by=None, limit=None, columns=None):
    print(f"\n--- Contents of '{table_name}' table ---")
    cursor = conn.cursor()
    try:
        cols = ', '.join(columns) if columns else '*'
        query = f"SELECT {cols} FROM {table_name}"
        if order_by:
            query += f" ORDER BY {order_by} DESC"
        if limit:
            query += f" LIMIT {limit}"
        cursor.execute(query)
        rows = cursor.fetchall()
        if not rows:
            print(f"No data found in {table_name}.")
            return

        # Get column names
        column_names = columns if columns else [description[0] for description in cursor.description]
        print(" | ".join(column_names))
        print("-" * (sum(len(name) for name in column_names) + (len(column_names) - 1) * 3)) # Dynamic separator

        for row in rows:
            print(" | ".join(str(col) for col in row))

    except sqlite3.Error as e:
        print(f"An error occurred with table {table_name}: {e}")
    finally:
        cursor.close()

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file not found at: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"Successfully connected to database: {DB_PATH}")

        print_table_data("tasks", conn, order_by="updated_at")
        print_table_data(
            "thoughts", conn,
            order_by="updated_at",
            limit=30,
            columns=["thought_id", "source_task_id", "thought_type", "status", "created_at", "updated_at"]
        )

    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()
