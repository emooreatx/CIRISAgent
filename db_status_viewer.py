import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ciris_engine", "data", "ciris_engine.db")

def print_table_data(table_name, conn):
    print(f"\n--- Contents of '{table_name}' table ---")
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        if not rows:
            print(f"No data found in {table_name}.")
            return

        # Get column names
        column_names = [description[0] for description in cursor.description]
        print(" | ".join(column_names))
        print("-" * (sum(len(name) for name in column_names) + (len(column_names) - 1) * 3)) # Dynamic separator

        for row_idx, row in enumerate(rows):
            # Truncate long string columns for better display, e.g., 'content' or 'context'
            display_row = []
            for i, col_value in enumerate(row):
                col_name = column_names[i]
                if isinstance(col_value, str) and (col_name == "content" or col_name == "context" or col_name == "processing_context" or col_name == "action_parameters" or col_name == "final_action_result"):
                    display_row.append(col_value[:70] + "..." if len(col_value) > 70 else col_value)
                else:
                    display_row.append(str(col_value))
            print(" | ".join(display_row))
            if row_idx > 20 and table_name == "thoughts": # Limit thoughts display
                print(f"... and {len(rows) - row_idx -1} more rows in thoughts table.")
                break
        if not rows:
            print(f"No data in {table_name} table.")

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

        print_table_data("tasks", conn)
        print_table_data("thoughts", conn)

    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()
