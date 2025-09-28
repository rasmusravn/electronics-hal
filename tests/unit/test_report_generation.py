"""Unit tests for report generation functionality."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from hal.config_models import PathsConfig, SystemConfig
from hal.database_manager import DatabaseManager
from hal.reports.generators import HTMLReportGenerator, JSONReportGenerator
from hal.reports.models import (
    MeasurementSummary,
    ReportData,
    TestResultSummary,
    TestRunSummary,
)
from hal.reports.report_manager import ReportManager


class TestReportModels:
    """Test report data models."""

    def test_measurement_summary_from_db_row(self):
        """Test MeasurementSummary creation from database row."""
        db_row = {
            "measurement_id": 1,
            "name": "voltage",
            "value": 5.0,
            "unit": "V",
            "limits": '{"min": 4.5, "max": 5.5}',
            "timestamp": "2024-01-01T12:00:00",
            "passed": 1
        }

        measurement = MeasurementSummary.from_db_row(db_row)

        assert measurement.measurement_id == 1
        assert measurement.name == "voltage"
        assert measurement.value == 5.0
        assert measurement.unit == "V"
        assert measurement.limits == {"min": 4.5, "max": 5.5}
        assert measurement.passed is True

    def test_measurement_summary_no_limits(self):
        """Test MeasurementSummary with no limits."""
        db_row = {
            "measurement_id": 1,
            "name": "voltage",
            "value": 5.0,
            "unit": "V",
            "limits": None,
            "timestamp": "2024-01-01T12:00:00",
            "passed": 1
        }

        measurement = MeasurementSummary.from_db_row(db_row)
        assert measurement.limits is None

    def test_test_result_summary_from_db_row(self):
        """Test TestResultSummary creation from database row."""
        db_row = {
            "result_id": 1,
            "test_name": "test_voltage_regulation",
            "outcome": "PASSED",
            "start_time": "2024-01-01T12:00:00",
            "duration": 2.5,
            "logs": "Test completed successfully",
            "error_message": None
        }

        result = TestResultSummary.from_db_row(db_row)

        assert result.result_id == 1
        assert result.test_name == "test_voltage_regulation"
        assert result.outcome == "PASSED"
        assert result.duration == 2.5
        assert result.logs == "Test completed successfully"

    def test_test_result_summary_measurement_counts(self):
        """Test measurement counting properties."""
        result = TestResultSummary(
            result_id=1,
            test_name="test",
            outcome="PASSED",
            start_time=datetime.now(),
            duration=1.0
        )

        # Add some measurements
        result.measurements = [
            MeasurementSummary(
                measurement_id=1,
                name="test1",
                value=1.0,
                unit="V",
                timestamp=datetime.now(),
                passed=True
            ),
            MeasurementSummary(
                measurement_id=2,
                name="test2",
                value=2.0,
                unit="V",
                timestamp=datetime.now(),
                passed=False
            ),
            MeasurementSummary(
                measurement_id=3,
                name="test3",
                value=3.0,
                unit="V",
                timestamp=datetime.now(),
                passed=True
            )
        ]

        assert result.total_measurements == 3
        assert result.passed_measurements == 2
        assert result.failed_measurements == 1

    def test_test_run_summary_properties(self):
        """Test TestRunSummary calculated properties."""
        # Use fixed times to avoid timing issues
        start_time = datetime(2024, 1, 1, 12, 0, 0)
        end_time = datetime(2024, 1, 1, 13, 0, 0)

        run = TestRunSummary(
            run_id="test-run",
            start_time=start_time,
            end_time=end_time,
            status="COMPLETED",
            configuration_snapshot={},
            total_tests=10,
            passed_tests=8,
            failed_tests=2
        )

        assert run.duration == 3600.0  # Exactly 1 hour
        assert run.success_rate == 80.0

    def test_report_data_properties(self):
        """Test ReportData calculated properties."""
        test_run = TestRunSummary(
            run_id="test-run",
            start_time=datetime.now(),
            status="COMPLETED",
            configuration_snapshot={},
            total_tests=2,
            passed_tests=1,
            failed_tests=1
        )

        # Add test results
        failed_test = TestResultSummary(
            result_id=1,
            test_name="failed_test",
            outcome="FAILED",
            start_time=datetime.now(),
            duration=1.0
        )

        passed_test = TestResultSummary(
            result_id=2,
            test_name="passed_test",
            outcome="PASSED",
            start_time=datetime.now(),
            duration=1.0
        )

        test_run.test_results = [failed_test, passed_test]
        report_data = ReportData(test_run=test_run)

        assert len(report_data.failed_tests) == 1
        assert report_data.failed_tests[0].test_name == "failed_test"


class TestJSONReportGenerator:
    """Test JSON report generator."""

    def test_json_generation(self):
        """Test JSON report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            generator = JSONReportGenerator(Path(temp_dir))

            # Create test data
            test_run = TestRunSummary(
                run_id="test-run",
                start_time=datetime.now(),
                status="COMPLETED",
                configuration_snapshot={"test": "config"},
                total_tests=1,
                passed_tests=1
            )

            test_result = TestResultSummary(
                result_id=1,
                test_name="test_example",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0
            )

            measurement = MeasurementSummary(
                measurement_id=1,
                name="voltage",
                value=5.0,
                unit="V",
                timestamp=datetime.now(),
                passed=True
            )

            test_result.measurements = [measurement]
            test_run.test_results = [test_result]
            report_data = ReportData(test_run=test_run)

            # Generate report
            output_path = generator.generate(report_data, "test_report")

            # Verify file exists and contains valid JSON
            assert output_path.exists()
            assert output_path.suffix == ".json"

            with open(output_path) as f:
                data = json.load(f)

            assert data["test_run"]["run_id"] == "test-run"
            assert data["test_run"]["status"] == "COMPLETED"
            assert len(data["test_run"]["test_results"]) == 1


class TestHTMLReportGenerator:
    """Test HTML report generator."""

    def test_html_generation(self):
        """Test HTML report generation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            generator = HTMLReportGenerator(Path(temp_dir))

            # Create test data
            test_run = TestRunSummary(
                run_id="test-run",
                start_time=datetime.now(),
                status="COMPLETED",
                configuration_snapshot={"test": "config"},
                total_tests=1,
                passed_tests=1
            )

            test_result = TestResultSummary(
                result_id=1,
                test_name="test_example",
                outcome="PASSED",
                start_time=datetime.now(),
                duration=1.0
            )

            test_run.test_results = [test_result]
            report_data = ReportData(test_run=test_run)

            # Generate report
            output_path = generator.generate(report_data, "test_report")

            # Verify file exists and contains HTML
            assert output_path.exists()
            assert output_path.suffix == ".html"

            with open(output_path) as f:
                content = f.read()

            assert "<!DOCTYPE html>" in content
            assert "Electronics HAL Test Report" in content
            assert "test-run" in content


class TestReportManager:
    """Test report manager functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create a mock database manager."""
        db_manager = Mock(spec=DatabaseManager)
        db_manager._connection = Mock()
        return db_manager

    @pytest.fixture
    def test_config(self):
        """Create test configuration."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = SystemConfig()
            config.paths = PathsConfig(
                log_dir=Path(temp_dir) / "logs",
                report_dir=Path(temp_dir) / "reports",
                db_path=Path(temp_dir) / "test.db"
            )
            yield config

    def test_get_available_test_runs(self, mock_db_manager, test_config):
        """Test getting available test runs."""
        # Setup mock data
        mock_cursor = Mock()
        mock_db_manager._connection.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                'run_id': 'run1',
                'start_time': '2024-01-01T12:00:00',
                'end_time': '2024-01-01T13:00:00',
                'status': 'COMPLETED',
                'total_tests': 5,
                'passed_tests': 4,
                'failed_tests': 1
            }
        ]

        manager = ReportManager(mock_db_manager, test_config)
        runs = manager.get_available_test_runs()

        assert len(runs) == 1
        assert runs[0]['run_id'] == 'run1'
        assert runs[0]['duration'] == 3600.0  # 1 hour

    def test_load_test_run_data(self, mock_db_manager, test_config):
        """Test loading complete test run data."""
        # Setup mock data
        run_data = {
            'run_id': 'test-run',
            'start_time': '2024-01-01T12:00:00',
            'end_time': '2024-01-01T13:00:00',
            'status': 'COMPLETED',
            'configuration_snapshot': '{"test": "config"}',
            'total_tests': 1,
            'passed_tests': 1,
            'failed_tests': 0,
            'skipped_tests': 0
        }

        test_results_data = [{
            'result_id': 1,
            'test_name': 'test_example',
            'outcome': 'PASSED',
            'start_time': '2024-01-01T12:00:00',
            'duration': 1.0,
            'logs': None,
            'error_message': None
        }]

        measurements_data = [{
            'measurement_id': 1,
            'name': 'voltage',
            'value': 5.0,
            'unit': 'V',
            'limits': '{"min": 4.5, "max": 5.5}',
            'timestamp': '2024-01-01T12:00:00',
            'passed': 1
        }]

        mock_db_manager.get_test_run.return_value = run_data
        mock_db_manager.get_test_results.return_value = test_results_data
        mock_db_manager.get_measurements.return_value = measurements_data

        manager = ReportManager(mock_db_manager, test_config)
        report_data = manager.load_test_run_data('test-run')

        assert report_data.test_run.run_id == 'test-run'
        assert len(report_data.test_run.test_results) == 1
        assert len(report_data.test_run.test_results[0].measurements) == 1

    def test_load_test_run_data_not_found(self, mock_db_manager, test_config):
        """Test loading test run data when run doesn't exist."""
        mock_db_manager.get_test_run.return_value = None

        manager = ReportManager(mock_db_manager, test_config)

        with pytest.raises(ValueError, match="Test run .* not found"):
            manager.load_test_run_data('nonexistent-run')

    def test_generate_report(self, mock_db_manager, test_config):
        """Test report generation."""
        # Setup mock data (abbreviated for brevity)
        run_data = {
            'run_id': 'test-run',
            'start_time': '2024-01-01T12:00:00',
            'status': 'COMPLETED',
            'configuration_snapshot': '{}',
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'skipped_tests': 0
        }

        mock_db_manager.get_test_run.return_value = run_data
        mock_db_manager.get_test_results.return_value = []

        manager = ReportManager(mock_db_manager, test_config)

        # Generate JSON report
        generated = manager.generate_report('test-run', ['json'])

        assert 'json' in generated
        assert generated['json'].exists()

    def test_generate_report_invalid_format(self, mock_db_manager, test_config):
        """Test error handling for invalid format."""
        manager = ReportManager(mock_db_manager, test_config)

        with pytest.raises(ValueError, match="Invalid formats"):
            manager.generate_report('test-run', ['invalid'])


if __name__ == '__main__':
    pytest.main([__file__])
