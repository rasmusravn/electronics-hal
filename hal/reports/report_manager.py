"""Report manager for orchestrating report generation."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config_models import SystemConfig
from ..file_storage_manager import FileSystemStorage
from .generators import HTMLReportGenerator, JSONReportGenerator, PDFReportGenerator
from .models import MeasurementSummary, ReportData, TestResultSummary, TestRunSummary


class ReportManager:
    """
    Manages report generation from test results file storage.

    This class provides a high-level interface for generating reports
    in various formats from test execution data.
    """

    def __init__(self, storage_manager: FileSystemStorage, config: SystemConfig):
        """
        Initialize report manager.

        Args:
            storage_manager: File system storage manager instance
            config: System configuration
        """
        self.storage_manager = storage_manager
        self.config = config
        self.output_dir = config.paths.report_dir

        # Initialize generators
        self.generators = {
            'json': JSONReportGenerator(self.output_dir),
            'html': HTMLReportGenerator(self.output_dir),
            'pdf': PDFReportGenerator(self.output_dir)
        }

    def get_available_test_runs(self) -> List[Dict[str, Any]]:
        """
        Get list of all available test runs.

        Returns:
            List of test run summary dictionaries
        """
        return self.storage_manager.get_available_test_runs()

    def load_test_run_data(self, run_id: str) -> ReportData:
        """
        Load complete test run data for report generation.

        Args:
            run_id: Test run identifier

        Returns:
            Complete report data structure

        Raises:
            ValueError: If test run not found
        """
        # Get test run info
        run_data = self.storage_manager.get_test_run(run_id)
        if not run_data:
            raise ValueError(f"Test run {run_id} not found")

        # Create test run summary (adapt from file format)
        test_run = TestRunSummary.from_file_data(run_data)

        # Get all test results for this run
        test_results_data = self.storage_manager.get_test_results(run_id)
        test_results = []

        for result_data in test_results_data:
            test_result = TestResultSummary.from_file_data(result_data)

            # Get measurements for this test result
            measurements_data = result_data.get("measurements", [])
            measurements = [
                MeasurementSummary.from_file_data(meas_data)
                for meas_data in measurements_data
            ]
            test_result.measurements = measurements
            test_results.append(test_result)

        test_run.test_results = test_results

        # Update test counts if they're not set
        if test_run.total_tests == 0:
            test_run.total_tests = len(test_results)
            test_run.passed_tests = sum(1 for t in test_results if t.outcome == 'PASSED')
            test_run.failed_tests = sum(1 for t in test_results if t.outcome == 'FAILED')
            test_run.skipped_tests = sum(1 for t in test_results if t.outcome == 'SKIPPED')

        return ReportData(test_run=test_run)

    def generate_report(
        self,
        run_id: str,
        formats: List[str],
        filename: Optional[str] = None
    ) -> Dict[str, Path]:
        """
        Generate reports in specified formats.

        Args:
            run_id: Test run identifier
            formats: List of format names ('json', 'html', 'pdf')
            filename: Optional custom filename (without extension)

        Returns:
            Dictionary mapping format to generated file path

        Raises:
            ValueError: If invalid format specified or test run not found
        """
        # Validate formats
        invalid_formats = set(formats) - set(self.generators.keys())
        if invalid_formats:
            raise ValueError(f"Invalid formats: {invalid_formats}. Available: {list(self.generators.keys())}")

        # Load test run data
        report_data = self.load_test_run_data(run_id)

        # Generate default filename if not provided
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_report_{run_id[:8]}_{timestamp}"

        # Generate reports
        generated_files = {}
        for format_name in formats:
            generator = self.generators[format_name]
            try:
                file_path = generator.generate(report_data, filename)
                generated_files[format_name] = file_path
                print(f"Generated {format_name.upper()} report: {file_path}")
            except Exception as e:
                print(f"Error generating {format_name} report: {e}")
                # Continue with other formats even if one fails

        return generated_files

    def generate_latest_report(
        self,
        formats: List[str],
        filename: Optional[str] = None
    ) -> Dict[str, Path]:
        """
        Generate reports for the most recent test run.

        Args:
            formats: List of format names ('json', 'html', 'pdf')
            filename: Optional custom filename (without extension)

        Returns:
            Dictionary mapping format to generated file path

        Raises:
            ValueError: If no test runs found
        """
        runs = self.get_available_test_runs()
        if not runs:
            raise ValueError("No test runs found in database")

        latest_run = runs[0]  # Already sorted by start_time DESC
        return self.generate_report(latest_run['run_id'], formats, filename)

    def generate_all_reports(
        self,
        formats: List[str],
        max_runs: Optional[int] = None
    ) -> Dict[str, Dict[str, Path]]:
        """
        Generate reports for multiple test runs.

        Args:
            formats: List of format names ('json', 'html', 'pdf')
            max_runs: Maximum number of recent runs to process (None for all)

        Returns:
            Nested dictionary: {run_id: {format: file_path}}
        """
        runs = self.get_available_test_runs()

        if max_runs:
            runs = runs[:max_runs]

        all_generated = {}
        for run in runs:
            run_id = run['run_id']
            try:
                generated = self.generate_report(run_id, formats)
                all_generated[run_id] = generated
            except Exception as e:
                print(f"Error generating reports for run {run_id}: {e}")
                all_generated[run_id] = {}

        return all_generated

    def get_report_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Get a quick summary of a test run for display purposes.

        Args:
            run_id: Test run identifier

        Returns:
            Summary dictionary with key metrics
        """
        try:
            report_data = self.load_test_run_data(run_id)
            return report_data.summary_stats
        except Exception as e:
            return {"error": str(e)}

    def cleanup_old_reports(self, keep_days: int = 30) -> int:
        """
        Clean up old report files.

        Args:
            keep_days: Number of days of reports to keep

        Returns:
            Number of files deleted
        """
        cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
        deleted_count = 0

        for file_path in self.output_dir.glob("*"):
            if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {file_path}: {e}")

        return deleted_count
