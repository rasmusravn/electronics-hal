"""
Example script demonstrating report generation functionality.

This script shows how to use the report generation system to create
reports from test results data.
"""

import sys
from pathlib import Path

# Add the project root to the path so we can import hal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from hal.config_loader import load_config
from hal.file_storage_manager import FileSystemStorage
from hal.reports.report_manager import ReportManager


def main():
    """Demonstrate report generation."""
    try:
        # Load configuration
        config = load_config()
        print(f"Using test data directory: {config.paths.test_data_dir}")
        print(f"Reports will be saved to: {config.paths.report_dir}")

        # Create file system storage
        storage_manager = FileSystemStorage(config.paths.test_data_dir)

        # Create report manager
        report_manager = ReportManager(storage_manager, config)

        # List available test runs
        print("\nAvailable test runs:")
        runs = report_manager.get_available_test_runs()

        if not runs:
            print("No test runs found. Please run some tests first using pytest.")
            return

        print(f"Found {len(runs)} test run(s):")
        for i, run in enumerate(runs[:5]):  # Show first 5
            duration = "N/A"
            if run.get('duration'):
                duration = f"{run['duration']:.1f}s"

            print(f"  {i+1}. {run['run_id'][:20]}... - "
                  f"Status: {run['status']} - "
                  f"Tests: {run.get('total_tests', 0)} - "
                  f"Duration: {duration}")

        # Generate report for the latest run
        print(f"\nGenerating reports for latest run: {runs[0]['run_id'][:20]}...")

        try:
            generated_files = report_manager.generate_latest_report(['json', 'html'])

            print("\nSuccessfully generated:")
            for format_name, file_path in generated_files.items():
                print(f"  {format_name.upper()}: {file_path}")

            # Show summary
            summary = report_manager.get_report_summary(runs[0]['run_id'])
            print(f"\nTest Summary:")
            print(f"  Total Tests: {summary.get('total_tests', 0)}")
            print(f"  Passed: {summary.get('passed_tests', 0)}")
            print(f"  Failed: {summary.get('failed_tests', 0)}")
            print(f"  Success Rate: {summary.get('success_rate', 0):.1f}%")
            print(f"  Total Measurements: {summary.get('total_measurements', 0)}")
            print(f"  Measurement Success Rate: {summary.get('measurement_success_rate', 0):.1f}%")

        except Exception as e:
            print(f"Error generating report: {e}")

    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())