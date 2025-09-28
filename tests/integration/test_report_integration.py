"""Integration tests for complete report generation workflow."""

import json
import tempfile
from pathlib import Path

import pytest

from hal.config_models import PathsConfig, SystemConfig
from hal.database_manager import DatabaseManager
from hal.reports.report_manager import ReportManager


class TestReportIntegration:
    """Integration tests for report generation with real database."""

    @pytest.fixture
    def test_db_setup(self):
        """Create a test database with sample data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create config
            config = SystemConfig()
            config.paths = PathsConfig(
                log_dir=temp_path / "logs",
                report_dir=temp_path / "reports",
                db_path=temp_path / "test.db"
            )

            # Create database and add test data
            db_manager = DatabaseManager(config.paths.db_path)
            db_manager.connect()

            # Create test run
            run_id = "test-integration-run"
            db_manager.create_test_run(run_id, config)

            # Add test results
            result_id1 = db_manager.create_test_result(run_id, "test_voltage_regulation")
            db_manager.update_test_result(result_id1, "PASSED", 2.5)
            db_manager.add_measurement(result_id1, "output_voltage", 5.0, "V", {"min": 4.9, "max": 5.1})
            db_manager.add_measurement(result_id1, "ripple", 0.01, "V", {"max": 0.05})

            result_id2 = db_manager.create_test_result(run_id, "test_current_limit")
            db_manager.update_test_result(result_id2, "FAILED", 1.8, error_message="Current exceeded limit")
            db_manager.add_measurement(result_id2, "max_current", 2.5, "A", {"max": 2.0})

            # Update test run with final counts
            db_manager.update_test_run(run_id, "COMPLETED", total_tests=2, passed_tests=1, failed_tests=1)

            yield config, db_manager, run_id

            db_manager.disconnect()

    def test_complete_report_generation_workflow(self, test_db_setup):
        """Test the complete workflow from database to reports."""
        config, db_manager, run_id = test_db_setup

        # Create report manager
        report_manager = ReportManager(db_manager, config)

        # Test getting available runs
        runs = report_manager.get_available_test_runs()
        assert len(runs) == 1
        assert runs[0]['run_id'] == run_id

        # Test loading complete data
        report_data = report_manager.load_test_run_data(run_id)
        assert report_data.test_run.run_id == run_id
        assert report_data.test_run.total_tests == 2
        assert report_data.test_run.passed_tests == 1
        assert report_data.test_run.failed_tests == 1
        assert len(report_data.test_run.test_results) == 2

        # Verify measurements are loaded
        voltage_test = next((t for t in report_data.test_run.test_results if t.test_name == "test_voltage_regulation"), None)
        assert voltage_test is not None
        assert len(voltage_test.measurements) == 2
        assert voltage_test.passed_measurements == 2
        assert voltage_test.failed_measurements == 0

        current_test = next((t for t in report_data.test_run.test_results if t.test_name == "test_current_limit"), None)
        assert current_test is not None
        assert len(current_test.measurements) == 1
        assert current_test.passed_measurements == 0
        assert current_test.failed_measurements == 1

        # Test report generation
        generated_files = report_manager.generate_report(run_id, ['json', 'html'])

        # Verify files were created
        assert 'json' in generated_files
        assert 'html' in generated_files
        assert generated_files['json'].exists()
        assert generated_files['html'].exists()

        # Verify JSON content
        with open(generated_files['json']) as f:
            json_data = json.load(f)

        assert json_data['test_run']['run_id'] == run_id
        assert json_data['test_run']['total_tests'] == 2
        assert len(json_data['test_run']['test_results']) == 2
        assert json_data['summary_stats']['success_rate'] == 50.0
        assert abs(json_data['summary_stats']['measurement_success_rate'] - 66.66666666666667) < 0.001  # 2/3 measurements passed

        # Verify HTML content structure
        with open(generated_files['html']) as f:
            html_content = f.read()

        assert "Electronics HAL Test Report" in html_content
        assert run_id in html_content
        assert "test_voltage_regulation" in html_content
        assert "test_current_limit" in html_content
        assert "Current exceeded limit" in html_content

    def test_report_summary_properties(self, test_db_setup):
        """Test calculated summary properties."""
        config, db_manager, run_id = test_db_setup
        report_manager = ReportManager(db_manager, config)

        report_data = report_manager.load_test_run_data(run_id)

        # Test overall statistics
        assert report_data.test_run.success_rate == 50.0  # 1/2 tests passed
        assert report_data.test_run.total_measurements == 3  # 2 + 1 measurements
        assert report_data.test_run.passed_measurements == 2  # 2 voltage measurements passed
        assert report_data.test_run.failed_measurements == 1  # 1 current measurement failed
        assert abs(report_data.test_run.measurement_success_rate - 66.66666666666667) < 0.001  # 2/3

        # Test failed tests identification
        failed_tests = report_data.failed_tests
        assert len(failed_tests) == 1
        assert failed_tests[0].test_name == "test_current_limit"

        # Test failed measurements by test
        failed_by_test = report_data.failed_measurements_by_test
        assert "test_current_limit" in failed_by_test
        assert len(failed_by_test["test_current_limit"]) == 1
        assert failed_by_test["test_current_limit"][0].name == "max_current"

    def test_multiple_report_formats(self, test_db_setup):
        """Test generating all supported formats."""
        config, db_manager, run_id = test_db_setup
        report_manager = ReportManager(db_manager, config)

        # Generate all formats
        generated_files = report_manager.generate_report(run_id, ['json', 'html'])

        # Verify all files exist and have correct extensions
        assert generated_files['json'].suffix == '.json'
        assert generated_files['html'].suffix == '.html'

        # Verify file sizes (should have actual content)
        assert generated_files['json'].stat().st_size > 100
        assert generated_files['html'].stat().st_size > 1000  # HTML should be larger

    def test_latest_report_generation(self, test_db_setup):
        """Test generating report for latest test run."""
        config, db_manager, run_id = test_db_setup
        report_manager = ReportManager(db_manager, config)

        # Should work with our single test run
        generated_files = report_manager.generate_latest_report(['json'])
        assert 'json' in generated_files
        assert generated_files['json'].exists()

    def test_report_with_custom_filename(self, test_db_setup):
        """Test generating report with custom filename."""
        config, db_manager, run_id = test_db_setup
        report_manager = ReportManager(db_manager, config)

        generated_files = report_manager.generate_report(run_id, ['json'], 'custom_report_name')

        assert 'json' in generated_files
        assert generated_files['json'].name == 'custom_report_name.json'

    def test_cleanup_old_reports(self, test_db_setup):
        """Test cleanup of old report files."""
        config, db_manager, run_id = test_db_setup
        report_manager = ReportManager(db_manager, config)

        # Generate some reports
        report_manager.generate_report(run_id, ['json', 'html'])

        # Verify files exist
        report_files = list(config.paths.report_dir.glob('*'))
        assert len(report_files) >= 2

        # Cleanup with very short retention (0 days = delete all)
        deleted_count = report_manager.cleanup_old_reports(keep_days=0)
        assert deleted_count >= 2

        # Verify files are gone
        remaining_files = list(config.paths.report_dir.glob('*'))
        assert len(remaining_files) == 0


@pytest.mark.parametrize("format_name", ["json", "html"])
def test_individual_format_generation(format_name):
    """Test individual format generation with parametrized test."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Setup minimal test environment
        config = SystemConfig()
        config.paths = PathsConfig(
            log_dir=temp_path / "logs",
            report_dir=temp_path / "reports",
            db_path=temp_path / "test.db"
        )

        db_manager = DatabaseManager(config.paths.db_path)
        db_manager.connect()

        run_id = "param-test-run"
        db_manager.create_test_run(run_id, config)
        result_id = db_manager.create_test_result(run_id, "simple_test")
        db_manager.update_test_result(result_id, "PASSED", 1.0)
        db_manager.update_test_run(run_id, "COMPLETED", total_tests=1, passed_tests=1)

        try:
            report_manager = ReportManager(db_manager, config)
            generated_files = report_manager.generate_report(run_id, [format_name])

            assert format_name in generated_files
            assert generated_files[format_name].exists()
            assert generated_files[format_name].suffix == f'.{format_name}'

        finally:
            db_manager.disconnect()


if __name__ == '__main__':
    pytest.main([__file__])
