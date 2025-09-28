"""Command-line interface for report generation."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from ..config_loader import load_config
from ..database_manager import DatabaseManager
from .report_manager import ReportManager


def create_parser() -> argparse.ArgumentParser:
    """Create the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Generate test reports from Electronics HAL test results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate HTML report for latest test run
  python -m hal.reports.cli --latest --format html

  # Generate all formats for specific run
  python -m hal.reports.cli --run-id abc123-def456 --format json html pdf

  # List available test runs
  python -m hal.reports.cli --list

  # Generate reports for all recent runs
  python -m hal.reports.cli --all --max-runs 5 --format html

  # Custom output filename
  python -m hal.reports.cli --latest --format html --output my_report
        """
    )

    # Report generation options
    generation_group = parser.add_mutually_exclusive_group(required=True)
    generation_group.add_argument(
        '--run-id',
        help='Generate report for specific test run ID'
    )
    generation_group.add_argument(
        '--latest',
        action='store_true',
        help='Generate report for the most recent test run'
    )
    generation_group.add_argument(
        '--all',
        action='store_true',
        help='Generate reports for multiple test runs'
    )
    generation_group.add_argument(
        '--list',
        action='store_true',
        help='List available test runs and exit'
    )

    # Format options
    parser.add_argument(
        '--format',
        choices=['json', 'html', 'pdf'],
        nargs='+',
        default=['html'],
        help='Report format(s) to generate (default: html)'
    )

    # Output options
    parser.add_argument(
        '--output',
        help='Custom filename (without extension)'
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        help='Custom output directory (overrides config)'
    )

    # Multi-run options
    parser.add_argument(
        '--max-runs',
        type=int,
        default=10,
        help='Maximum number of runs to process when using --all (default: 10)'
    )

    # Database options
    parser.add_argument(
        '--database',
        type=Path,
        help='Path to test results database (overrides config)'
    )

    # Other options
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output messages'
    )

    parser.add_argument(
        '--cleanup',
        type=int,
        metavar='DAYS',
        help='Clean up reports older than DAYS days'
    )

    return parser


def list_test_runs(report_manager: ReportManager, quiet: bool = False) -> None:
    """List available test runs."""
    runs = report_manager.get_available_test_runs()

    if not runs:
        if not quiet:
            print("No test runs found in database.")
        return

    if not quiet:
        print(f"Found {len(runs)} test run(s):\n")
        print(f"{'Run ID':<40} {'Status':<12} {'Start Time':<20} {'Duration':<10} {'Tests':<8}")
        print("-" * 100)

    for run in runs:
        run_id = run['run_id']
        status = run.get('status', 'UNKNOWN')
        start_time = run['start_time'][:19]  # Remove microseconds
        duration = format_duration(run.get('duration'))
        total_tests = run.get('total_tests', 0)
        passed_tests = run.get('passed_tests', 0)
        failed_tests = run.get('failed_tests', 0)

        tests_info = f"{passed_tests}P/{failed_tests}F/{total_tests}T"

        if not quiet:
            print(f"{run_id:<40} {status:<12} {start_time:<20} {duration:<10} {tests_info:<8}")


def format_duration(duration: Optional[float]) -> str:
    """Format duration in a human-readable way."""
    if duration is None:
        return "N/A"

    if duration < 60:
        return f"{duration:.1f}s"
    elif duration < 3600:
        minutes = duration // 60
        seconds = duration % 60
        return f"{int(minutes)}m{seconds:.0f}s"
    else:
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        return f"{int(hours)}h{int(minutes)}m"


def main() -> int:
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()

    try:
        # Load configuration
        config = load_config()

        # Override database path if specified
        if args.database:
            config.paths.db_path = args.database

        # Override output directory if specified
        if args.output_dir:
            config.paths.report_dir = args.output_dir

        # Connect to database
        db_manager = DatabaseManager(config.paths.db_path)
        db_manager.connect()

        # Create report manager
        report_manager = ReportManager(db_manager, config)

        try:
            # Handle cleanup first if requested
            if args.cleanup:
                deleted_count = report_manager.cleanup_old_reports(args.cleanup)
                if not args.quiet:
                    print(f"Deleted {deleted_count} old report file(s)")

            # Handle list command
            if args.list:
                list_test_runs(report_manager, args.quiet)
                return 0

            # Handle report generation
            generated_files = {}

            if args.run_id:
                # Generate for specific run
                generated_files = report_manager.generate_report(
                    args.run_id,
                    args.format,
                    args.output
                )

            elif args.latest:
                # Generate for latest run
                generated_files = report_manager.generate_latest_report(
                    args.format,
                    args.output
                )

            elif args.all:
                # Generate for multiple runs
                all_generated = report_manager.generate_all_reports(
                    args.format,
                    args.max_runs
                )

                if not args.quiet:
                    print(f"Generated reports for {len(all_generated)} test run(s)")
                    for run_id, files in all_generated.items():
                        if files:
                            print(f"  {run_id}: {', '.join(files.keys())}")
                        else:
                            print(f"  {run_id}: Failed to generate")

                return 0

            # Report results for single run generation
            if generated_files and not args.quiet:
                print("Successfully generated:")
                for format_name, file_path in generated_files.items():
                    print(f"  {format_name.upper()}: {file_path}")
            elif not generated_files:
                print("No reports were generated")
                return 1

        finally:
            db_manager.disconnect()

    except KeyboardInterrupt:
        if not args.quiet:
            print("\nOperation cancelled by user")
        return 130

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
