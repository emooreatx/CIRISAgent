import sqlite3
import os
import json
import argparse

DB_PATH = os.path.join(os.path.dirname(__file__), "ciris_engine", "data", "ciris_engine.db")

def get_thought_details_for_tasks(task_ids: list[str], conn):
    cursor = conn.cursor()
    results = {}

    for task_id in task_ids:
        print(f"\n--- Details for Task ID: {task_id} ---")
        try:
            cursor.execute(f"SELECT thought_id, content, processing_context_json, final_action_result_json, created_at, updated_at FROM thoughts WHERE source_task_id = ? ORDER BY created_at ASC", (task_id,))
            thoughts = cursor.fetchall()
            if not thoughts:
                print(f"No thoughts found for Task ID: {task_id}")
                results[task_id] = []
                continue

            task_thoughts = []
            for thought_row in thoughts:
                thought_id, content, processing_context_str, final_action_result_str, created_at, updated_at = thought_row
                
                print(f"\n  Thought ID: {thought_id}")
                print(f"  Created At: {created_at}, Updated At: {updated_at}")
                print(f"  Content: {content[:200] + '...' if len(content) > 200 else content}")

                processing_context = None
                if processing_context_str:
                    try:
                        processing_context = json.loads(processing_context_str)
                        print(f"  Processing Context JSON:")
                        print(json.dumps(processing_context, indent=2))
                    except json.JSONDecodeError:
                        print(f"  Processing Context (Error decoding JSON): {processing_context_str}")
                else:
                    print("  Processing Context: None")

                final_action_result = None
                if final_action_result_str:
                    try:
                        final_action_result = json.loads(final_action_result_str)
                        print(f"  Final Action Result JSON:")
                        print(json.dumps(final_action_result, indent=2))
                    except json.JSONDecodeError:
                        print(f"  Final Action Result (Error decoding JSON): {final_action_result_str}")
                else:
                    print("  Final Action Result: None")
                
                task_thoughts.append({
                    "thought_id": thought_id,
                    "content": content,
                    "processing_context": processing_context,
                    "final_action_result": final_action_result,
                    "created_at": created_at,
                    "updated_at": updated_at
                })
            results[task_id] = task_thoughts

        except sqlite3.Error as e:
            print(f"An error occurred while fetching thoughts for Task ID {task_id}: {e}")
            results[task_id] = {"error": str(e)}
        
    cursor.close()
    return results

def main():
    parser = argparse.ArgumentParser(description="Fetch and display thought details for specific task IDs.")
    parser.add_argument("task_ids", metavar="TASK_ID", type=str, nargs='+',
                        help="One or more task IDs to fetch details for.")
    
    args = parser.parse_args()

    if not os.path.exists(DB_PATH):
        print(f"Database file not found at: {DB_PATH}")
        return

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        print(f"Successfully connected to database: {DB_PATH}")
        
        get_thought_details_for_tasks(args.task_ids, conn)

    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    main()
