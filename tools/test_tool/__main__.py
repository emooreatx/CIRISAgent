"""Command-line interface for test tool."""

import argparse
from .runner import TestRunner
from .config import DEFAULT_COMPOSE_FILE


def main():
    parser = argparse.ArgumentParser(
        description="CIRIS Test Tool - Advanced Docker-based pytest runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests with coverage
  python -m tools.test_tool start --coverage
  
  # Run a specific test
  python -m tools.test_tool test tests/adapters/api/test_oauth_permissions.py::TestOAuthPermissions::test_oauth_user_creation
  
  # Run tests matching a pattern
  python -m tools.test_tool start --filter "oauth"
  
  # Check status
  python -m tools.test_tool status
  
  # Show errors only
  python -m tools.test_tool logs --errors
  
  # Run without rebuilding (faster)
  python -m tools.test_tool start --no-rebuild
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new test run")
    start_parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    start_parser.add_argument("--filter", help="Pytest -k filter pattern")
    start_parser.add_argument("--compose-file", default=DEFAULT_COMPOSE_FILE,
                            help="Docker compose file to use")
    start_parser.add_argument("--no-rebuild", action="store_true",
                            help="Skip rebuilding the container")
    start_parser.add_argument("--parallel", type=int, help="Number of parallel workers")
    start_parser.add_argument("-v", "--verbose", action="count", default=1,
                            help="Increase verbosity (can be used multiple times)")
    start_parser.add_argument("--markers", nargs="+", help="Pytest markers to filter by")
    
    # Test command (shortcut for running specific tests)
    test_parser = subparsers.add_parser("test", help="Run a specific test")
    test_parser.add_argument("test_path", help="Test file or specific test to run")
    test_parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    test_parser.add_argument("--no-rebuild", action="store_true",
                           help="Skip rebuilding the container")
    test_parser.add_argument("-v", "--verbose", action="count", default=1,
                           help="Increase verbosity")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check test run status")
    
    # Logs command  
    logs_parser = subparsers.add_parser("logs", help="Show test output")
    logs_parser.add_argument("--tail", type=int, default=50,
                           help="Number of lines to show (0 for all)")
    logs_parser.add_argument("--errors", action="store_true",
                           help="Show only errors and failures with context")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop current test run")
    
    # Results command
    results_parser = subparsers.add_parser("results", help="Show test results summary")
    
    args = parser.parse_args()
    runner = TestRunner()
    
    if args.command == "start":
        runner.start(
            coverage=args.coverage,
            filter_pattern=args.filter,
            compose_file=args.compose_file,
            rebuild=not args.no_rebuild,
            parallel=args.parallel,
            verbose=args.verbose,
            markers=args.markers
        )
    elif args.command == "test":
        runner.run_single_test(
            test_path=args.test_path,
            coverage=args.coverage,
            rebuild=not args.no_rebuild
        )
    elif args.command == "status":
        runner.show_status()
    elif args.command == "logs":
        runner.logs(tail=args.tail, errors_only=args.errors)
    elif args.command == "stop":
        runner.stop()
    elif args.command == "results":
        runner.results()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()