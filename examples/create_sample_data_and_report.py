"""
Example script demonstrating report generation with sample data.

This script creates sample test data and then generates reports in all formats.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add the project root to the path so we can import hal modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from hal.config_loader import load_config
from hal.file_storage_manager import FileSystemStorage
from hal.reports.report_manager import ReportManager


def create_sample_test_data(storage_manager: FileSystemStorage, config) -> str:
    """Create sample test data for demonstration."""

    # Create a test run
    run_id = "demo-test-run-2024"
    print(f"Creating test run: {run_id}")
    storage_manager.create_test_run(run_id, config)

    # Test 1: Voltage regulation test (PASSED)
    result_id1 = storage_manager.create_test_result(run_id, "test_voltage_regulation")
    storage_manager.add_measurement(result_id1, "output_voltage", 5.02, "V", {"min": 4.95, "max": 5.05})
    storage_manager.add_measurement(result_id1, "ripple_voltage", 0.003, "V", {"max": 0.01})
    storage_manager.add_measurement(result_id1, "load_regulation", 0.15, "%", {"max": 0.5})
    storage_manager.update_test_result(result_id1, "PASSED", 2.1)

    # Test 2: Current limiting test (FAILED)
    result_id2 = storage_manager.create_test_result(run_id, "test_current_limiting")
    storage_manager.add_measurement(result_id2, "max_current", 2.8, "A", {"max": 2.5})
    storage_manager.add_measurement(result_id2, "current_accuracy", 2.1, "%", {"max": 2.0})
    storage_manager.update_test_result(result_id2, "FAILED", 1.8, error_message="Current limit exceeded")

    # Test 3: Signal generation test (PASSED)
    result_id3 = storage_manager.create_test_result(run_id, "test_signal_generation")
    storage_manager.add_measurement(result_id3, "frequency", 1000.1, "Hz", {"min": 999.0, "max": 1001.0})
    storage_manager.add_measurement(result_id3, "amplitude", 3.28, "V", {"min": 3.2, "max": 3.4})
    storage_manager.add_measurement(result_id3, "thd", 0.02, "%", {"max": 0.05})
    storage_manager.update_test_result(result_id3, "PASSED", 3.2)

    # Test 4: DMM accuracy test (PASSED)
    result_id4 = storage_manager.create_test_result(run_id, "test_dmm_accuracy")
    storage_manager.add_measurement(result_id4, "dc_accuracy", 0.012, "%", {"max": 0.02})
    storage_manager.add_measurement(result_id4, "ac_accuracy", 0.045, "%", {"max": 0.05})
    storage_manager.update_test_result(result_id4, "PASSED", 1.5)

    # Test 5: Power efficiency test (SKIPPED)
    result_id5 = storage_manager.create_test_result(run_id, "test_power_efficiency")
    storage_manager.update_test_result(result_id5, "SKIPPED", 0.0, error_message="Hardware not available")

    # Update test run with final counts
    storage_manager.update_test_run(run_id, "COMPLETED",
                                   total_tests=5,
                                   passed_tests=3,
                                   failed_tests=1,
                                   skipped_tests=1)

    return run_id


def main():
    """Create sample data and generate reports."""
    try:
        # Load configuration
        config = load_config()
        print(f"Using test data directory: {config.paths.test_data_dir}")
        print(f"Reports will be saved to: {config.paths.report_dir}")

        # Create file system storage
        storage_manager = FileSystemStorage(config.paths.test_data_dir)

        # Create sample test data
        run_id = create_sample_test_data(storage_manager, config)
        print(f"Created sample test data for run: {run_id}")

        # Create report manager
        report_manager = ReportManager(storage_manager, config)

        # List available test runs
        print("\nAvailable test runs:")
        runs = report_manager.get_available_test_runs()
        for i, run in enumerate(runs):
            duration = "N/A"
            if run.get('duration'):
                duration = f"{run['duration']:.1f}s"

            print(f"  {i+1}. {run['run_id']} - "
                  f"Status: {run['status']} - "
                  f"Tests: {run.get('total_tests', 0)} - "
                  f"Duration: {duration}")

            # Generate reports in all formats
            print(f"\nGenerating reports for run: {run_id}")
            try:
                generated_files = report_manager.generate_report(run_id, ['json', 'html'])

                print("\nSuccessfully generated:")
                for format_name, file_path in generated_files.items():
                    print(f"  {format_name.upper()}: {file_path}")

                # Show summary
                summary = report_manager.get_report_summary(run_id)
                print(f"\nTest Summary:")
                print(f"  Total Tests: {summary.get('total_tests', 0)}")
                print(f"  Passed: {summary.get('passed_tests', 0)}")
                print(f"  Failed: {summary.get('failed_tests', 0)}")
                print(f"  Skipped: {summary.get('skipped_tests', 0)}")
                print(f"  Success Rate: {summary.get('success_rate', 0):.1f}%")
                print(f"  Total Measurements: {summary.get('total_measurements', 0)}")
                print(f"  Measurement Success Rate: {summary.get('measurement_success_rate', 0):.1f}%")

                print(f"\nReport files have been created in: {config.paths.report_dir}")
                print("You can open the HTML report in a web browser to view the detailed results.")

            except Exception as e:
                print(f"Error generating reports: {e}")
                return 1


    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())