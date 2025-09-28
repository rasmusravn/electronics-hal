"""Data models for report generation."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MeasurementSummary(BaseModel):
    """Summary of a single measurement."""

    measurement_id: int
    name: str
    value: float
    unit: str
    limits: Optional[Dict[str, float]] = None
    timestamp: datetime
    passed: bool

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "MeasurementSummary":
        """Create from database row."""
        limits = None
        if row.get("limits"):
            limits = json.loads(row["limits"])

        return cls(
            measurement_id=row["measurement_id"],
            name=row["name"],
            value=row["value"],
            unit=row["unit"],
            limits=limits,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            passed=bool(row["passed"])
        )

    @classmethod
    def from_file_data(cls, data: Dict[str, Any]) -> "MeasurementSummary":
        """Create from file system data."""
        return cls(
            measurement_id=0,  # Not used in file-based storage
            name=data["name"],
            value=data["value"],
            unit=data["unit"],
            limits=data.get("limits"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            passed=bool(data["passed"])
        )


class TestResultSummary(BaseModel):
    """Summary of a single test result."""

    result_id: int
    test_name: str
    outcome: str
    start_time: datetime
    duration: float
    logs: Optional[str] = None
    error_message: Optional[str] = None
    measurements: List[MeasurementSummary] = Field(default_factory=list)

    @property
    def passed_measurements(self) -> int:
        """Count of passed measurements."""
        return sum(1 for m in self.measurements if m.passed)

    @property
    def failed_measurements(self) -> int:
        """Count of failed measurements."""
        return sum(1 for m in self.measurements if not m.passed)

    @property
    def total_measurements(self) -> int:
        """Total count of measurements."""
        return len(self.measurements)

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TestResultSummary":
        """Create from database row."""
        return cls(
            result_id=row["result_id"],
            test_name=row["test_name"],
            outcome=row["outcome"],
            start_time=datetime.fromisoformat(row["start_time"]),
            duration=row["duration"],
            logs=row.get("logs"),
            error_message=row.get("error_message")
        )

    @classmethod
    def from_file_data(cls, data: Dict[str, Any]) -> "TestResultSummary":
        """Create from file system data."""
        return cls(
            result_id=0,  # Not used in file-based storage
            test_name=data["test_name"],
            outcome=data["outcome"],
            start_time=datetime.fromisoformat(data["start_time"]),
            duration=data["duration"],
            logs=data.get("logs"),
            error_message=data.get("error_message")
        )


class TestRunSummary(BaseModel):
    """Summary of an entire test run."""

    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str
    configuration_snapshot: Dict[str, Any]
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    test_results: List[TestResultSummary] = Field(default_factory=list)

    @property
    def duration(self) -> Optional[float]:
        """Total test run duration in seconds."""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def success_rate(self) -> float:
        """Success rate as a percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed_tests / self.total_tests) * 100

    @property
    def total_measurements(self) -> int:
        """Total count of all measurements across all tests."""
        return sum(result.total_measurements for result in self.test_results)

    @property
    def passed_measurements(self) -> int:
        """Count of all passed measurements across all tests."""
        return sum(result.passed_measurements for result in self.test_results)

    @property
    def failed_measurements(self) -> int:
        """Count of all failed measurements across all tests."""
        return sum(result.failed_measurements for result in self.test_results)

    @property
    def measurement_success_rate(self) -> float:
        """Measurement success rate as a percentage."""
        if self.total_measurements == 0:
            return 0.0
        return (self.passed_measurements / self.total_measurements) * 100

    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> "TestRunSummary":
        """Create from database row."""
        config = json.loads(row["configuration_snapshot"])
        end_time = None
        if row.get("end_time"):
            end_time = datetime.fromisoformat(row["end_time"])

        return cls(
            run_id=row["run_id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=end_time,
            status=row["status"],
            configuration_snapshot=config,
            total_tests=row.get("total_tests", 0),
            passed_tests=row.get("passed_tests", 0),
            failed_tests=row.get("failed_tests", 0),
            skipped_tests=row.get("skipped_tests", 0)
        )

    @classmethod
    def from_file_data(cls, data: Dict[str, Any]) -> "TestRunSummary":
        """Create from file system data."""
        end_time = None
        if data.get("end_time"):
            end_time = datetime.fromisoformat(data["end_time"])

        # Handle configuration snapshot - it might be a JSON string
        config_snapshot = data["configuration_snapshot"]
        if isinstance(config_snapshot, str):
            config_snapshot = json.loads(config_snapshot)

        return cls(
            run_id=data["run_id"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=end_time,
            status=data["status"],
            configuration_snapshot=config_snapshot,
            total_tests=data.get("total_tests", 0),
            passed_tests=data.get("passed_tests", 0),
            failed_tests=data.get("failed_tests", 0),
            skipped_tests=data.get("skipped_tests", 0)
        )


class ReportData(BaseModel):
    """Complete report data structure."""

    test_run: TestRunSummary
    generation_time: datetime = Field(default_factory=datetime.now)
    report_version: str = "1.0"

    @property
    def summary_stats(self) -> Dict[str, Any]:
        """High-level summary statistics."""
        return {
            "run_id": self.test_run.run_id,
            "status": self.test_run.status,
            "duration": self.test_run.duration,
            "total_tests": self.test_run.total_tests,
            "passed_tests": self.test_run.passed_tests,
            "failed_tests": self.test_run.failed_tests,
            "skipped_tests": self.test_run.skipped_tests,
            "success_rate": self.test_run.success_rate,
            "total_measurements": self.test_run.total_measurements,
            "passed_measurements": self.test_run.passed_measurements,
            "failed_measurements": self.test_run.failed_measurements,
            "measurement_success_rate": self.test_run.measurement_success_rate,
            "generation_time": self.generation_time,
            "report_version": self.report_version
        }

    @property
    def failed_tests(self) -> List[TestResultSummary]:
        """List of failed tests."""
        return [test for test in self.test_run.test_results if test.outcome == "FAILED"]

    @property
    def failed_measurements_by_test(self) -> Dict[str, List[MeasurementSummary]]:
        """Failed measurements grouped by test name."""
        failed_by_test = {}
        for test in self.test_run.test_results:
            failed_measurements = [m for m in test.measurements if not m.passed]
            if failed_measurements:
                failed_by_test[test.test_name] = failed_measurements
        return failed_by_test
