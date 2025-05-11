import asyncio
import argparse
import sys
import os

# Ensure 'src' is in the Python path to allow importing from ciris_engine and agents
# This assumes run_cli_student.py is in the project root (CIRISAgent/)
# and 'src' is a subdirectory.
project_root = os.path.dirname(os.path.abspath(__file__))
src_dir_path = os.path.join(project_root, 'src')
if src_dir_path not in sys.path:
    sys.path.insert(0, src_dir_path)

# Now we can import the main function from the cli agent
from agents.cli_agent import main as cli_main

async def run_student_cli():
    """
    Wrapper to run the CLI agent specifically with the 'student' profile.
    It re-uses the argument parsing from cli_agent.py for input_string and log_level,
    but forces the profile to 'student'.
    """
    parser = argparse.ArgumentParser(description="CIRIS Engine CLI Tool (Student Profile)")
    parser.add_argument("input_string", type=str, help="The input string to process.")
    parser.add_argument("--log-level", type=str, default="INFO", 
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
                        help="Logging level. Default: INFO")
    
    # Parse only the arguments this script defines
    args = parser.parse_args()

    # Create a new list of arguments to pass to the original cli_main
    # This will include the forced profile and the user-provided arguments.
    original_sys_argv = sys.argv
    try:
        # Construct sys.argv as cli_main expects it
        # sys.argv[0] is the script name, then the arguments
        # cli_main's parser expects "input_string", then optional "--profile", then optional "--log-level"
        
        # Start with the script name placeholder (cli_main won't use it directly, argparse handles it)
        simulated_argv = [original_sys_argv[0]] # or "src/agents/cli_agent.py"
        
        # Add the positional input_string
        simulated_argv.append(args.input_string)
        
        # Force the profile
        simulated_argv.extend(["--profile", "student"])
        
        # Add log-level
        simulated_argv.extend(["--log-level", args.log_level])

        sys.argv = simulated_argv
        
        print(f"Running CLI Agent with Student Profile for input: \"{args.input_string}\"")
        print(f"Simulated argv for cli_main: {sys.argv}")

        await cli_main()

    finally:
        sys.argv = original_sys_argv # Restore original sys.argv

if __name__ == "__main__":
    # Ensure necessary environment variables are set (as in cli_agent.py)
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set.")
    else:
        asyncio.run(run_student_cli())
