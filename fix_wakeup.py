#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/app/data/ciris_engine.db')
cursor = conn.cursor()

# Update the verify identity task to completed
cursor.execute("UPDATE tasks SET status = 'completed' WHERE task_id = 'VERIFY_IDENTITY_0e385d10-71fa-44c9-9684-945f8bf4b0fd'")
conn.commit()
print('Updated VERIFY_IDENTITY task to completed')

# Also update any related thoughts
cursor.execute("UPDATE thoughts SET status = 'completed' WHERE source_task_id = 'VERIFY_IDENTITY_0e385d10-71fa-44c9-9684-945f8bf4b0fd' AND status != 'completed'")
rows = cursor.rowcount
conn.commit()
print(f'Updated {rows} thoughts to completed')

conn.close()