"""File system-based storage for test results and measurements."""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_models import SystemConfig


class PathJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Path objects."""

    def default(self, obj):
        if isinstance(obj, Path):
            return str(obj)
        return super().default(obj)


class FileSystemStorage:
    """Manages file system operations for test results."""

    def __init__(self, base_path: Path):
        """
        Initialize file system storage manager.

        Args:
            base_path: Base directory for storing test results
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def create_test_run(self, run_id: str, config: SystemConfig) -> Path:
        """
        Create a new test run directory structure.

        Args:
            run_id: Unique identifier for the test run
            config: System configuration snapshot

        Returns:
            Path to the created test run directory
        """
        run_dir = self.base_path / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (run_dir / "test_results").mkdir(exist_ok=True)
        (run_dir / "measurements").mkdir(exist_ok=True)
        (run_dir / "logs").mkdir(exist_ok=True)
        (run_dir / "reports").mkdir(exist_ok=True)

        # Save metadata
        metadata = {
            "run_id": run_id,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "status": "IN_PROGRESS",
            "configuration_snapshot": config.model_dump(),
            "total_tests": 0,
            "passed_tests": 0,
            "failed_tests": 0,
            "skipped_tests": 0
        }

        metadata_file = run_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, cls=PathJSONEncoder)

        return run_dir

    def update_test_run(self, run_id: str, status: str, **kwargs: Any) -> None:
        """
        Update a test run metadata.

        Args:
            run_id: Test run identifier
            status: Final status of the test run
            **kwargs: Additional fields to update
        """
        run_dir = self.base_path / run_id
        metadata_file = run_dir / "metadata.json"

        if not metadata_file.exists():
            raise ValueError(f"Test run {run_id} not found")

        # Load existing metadata
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Update fields
        metadata["status"] = status
        metadata["end_time"] = datetime.now().isoformat()

        for key, value in kwargs.items():
            if key in ["total_tests", "passed_tests", "failed_tests", "skipped_tests"]:
                metadata[key] = value

        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, cls=PathJSONEncoder)

    def create_test_result(self, run_id: str, test_name: str) -> str:
        """
        Create a new test result record.

        Args:
            run_id: Test run identifier
            test_name: Name of the test

        Returns:
            result_id: Unique identifier for this test result
        """
        run_dir = self.base_path / run_id
        if not run_dir.exists():
            raise ValueError(f"Test run {run_id} not found")

        # Generate unique result ID
        result_id = f"{run_id}_{test_name}_{datetime.now().strftime('%H%M%S_%f')}"

        # Create test result file
        test_result = {
            "result_id": result_id,
            "run_id": run_id,
            "test_name": test_name,
            "outcome": "RUNNING",
            "start_time": datetime.now().isoformat(),
            "duration": 0.0,
            "logs": None,
            "error_message": None,
            "measurements": []
        }

        result_file = run_dir / "test_results" / f"{result_id}.json"
        with open(result_file, 'w') as f:
            json.dump(test_result, f, indent=2, cls=PathJSONEncoder)

        return result_id

    def update_test_result(
        self,
        result_id: str,
        outcome: str,
        duration: float,
        logs: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update a test result record.

        Args:
            result_id: Test result identifier
            outcome: Test outcome (PASSED, FAILED, SKIPPED)
            duration: Test execution time in seconds
            logs: Optional log summary
            error_message: Optional error message for failed tests
        """
        # Find the test result file
        result_file = self._find_test_result_file(result_id)
        if not result_file:
            raise ValueError(f"Test result {result_id} not found")

        # Load existing result
        with open(result_file, 'r') as f:
            test_result = json.load(f)

        # Update fields
        test_result["outcome"] = outcome
        test_result["duration"] = duration
        if logs:
            test_result["logs"] = logs
        if error_message:
            test_result["error_message"] = error_message

        # Save updated result
        with open(result_file, 'w') as f:
            json.dump(test_result, f, indent=2, cls=PathJSONEncoder)

    def add_measurement(
        self,
        result_id: str,
        name: str,
        value: float,
        unit: str,
        limits: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Add a measurement record.

        Args:
            result_id: Test result identifier
            name: Measurement name
            value: Measured value
            unit: Unit of measurement
            limits: Optional pass/fail limits
        """
        # Find the test result file
        result_file = self._find_test_result_file(result_id)
        if not result_file:
            raise ValueError(f"Test result {result_id} not found")

        # Load existing result
        with open(result_file, 'r') as f:
            test_result = json.load(f)

        # Check if measurement passes limits
        passed = True
        if limits:
            if "min" in limits and value < limits["min"]:
                passed = False
            if "max" in limits and value > limits["max"]:
                passed = False

        # Add measurement
        measurement = {
            "name": name,
            "value": value,
            "unit": unit,
            "limits": limits,
            "timestamp": datetime.now().isoformat(),
            "passed": passed
        }

        test_result["measurements"].append(measurement)

        # Save updated result
        with open(result_file, 'w') as f:
            json.dump(test_result, f, indent=2, cls=PathJSONEncoder)

        # Also save measurement to separate CSV file for easy analysis
        run_id = test_result["run_id"]
        run_dir = self.base_path / run_id
        measurements_dir = run_dir / "measurements"

        csv_file = measurements_dir / f"{name}_measurements.csv"

        # Create CSV header if file doesn't exist
        if not csv_file.exists():
            with open(csv_file, 'w') as f:
                f.write("timestamp,test_name,value,unit,passed,min_limit,max_limit\n")

        # Append measurement
        with open(csv_file, 'a') as f:
            min_limit = limits.get("min", "") if limits else ""
            max_limit = limits.get("max", "") if limits else ""
            f.write(f"{measurement['timestamp']},{test_result['test_name']},{value},{unit},{passed},{min_limit},{max_limit}\n")

    def get_test_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get test run information.

        Args:
            run_id: Test run identifier

        Returns:
            Test run data or None if not found
        """
        run_dir = self.base_path / run_id
        metadata_file = run_dir / "metadata.json"

        if not metadata_file.exists():
            return None

        with open(metadata_file, 'r') as f:
            return json.load(f)

    def get_test_results(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all test results for a run.

        Args:
            run_id: Test run identifier

        Returns:
            List of test result records
        """
        run_dir = self.base_path / run_id
        results_dir = run_dir / "test_results"

        if not results_dir.exists():
            return []

        results = []
        for result_file in results_dir.glob("*.json"):
            with open(result_file, 'r') as f:
                result = json.load(f)
                results.append(result)

        # Sort by start time
        results.sort(key=lambda x: x.get("start_time", ""))
        return results

    def get_measurements(self, result_id: str) -> List[Dict[str, Any]]:
        """
        Get all measurements for a test result.

        Args:
            result_id: Test result identifier

        Returns:
            List of measurement records
        """
        result_file = self._find_test_result_file(result_id)
        if not result_file:
            return []

        with open(result_file, 'r') as f:
            test_result = json.load(f)

        return test_result.get("measurements", [])

    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a test run.

        Args:
            run_id: Test run identifier

        Returns:
            Summary statistics dictionary
        """
        # Get test run info
        run_info = self.get_test_run(run_id)
        if not run_info:
            return {}

        # Get test results
        test_results = self.get_test_results(run_id)

        # Calculate outcome counts
        outcome_counts = {}
        failed_measurements = 0

        for result in test_results:
            outcome = result.get("outcome", "UNKNOWN")
            outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1

            # Count failed measurements
            for measurement in result.get("measurements", []):
                if not measurement.get("passed", True):
                    failed_measurements += 1

        return {
            **run_info,
            "outcome_counts": outcome_counts,
            "failed_measurements": failed_measurements
        }

    def get_available_test_runs(self) -> List[Dict[str, Any]]:
        """
        Get list of all available test runs.

        Returns:
            List of test run summaries
        """
        runs = []

        for run_dir in self.base_path.iterdir():
            if not run_dir.is_dir():
                continue

            metadata_file = run_dir / "metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Calculate duration if end_time exists
                if metadata.get('end_time') and metadata.get('start_time'):
                    start = datetime.fromisoformat(metadata['start_time'])
                    end = datetime.fromisoformat(metadata['end_time'])
                    metadata['duration'] = (end - start).total_seconds()
                else:
                    metadata['duration'] = None

                runs.append(metadata)
            except (json.JSONDecodeError, KeyError):
                # Skip invalid metadata files
                continue

        # Sort by start time (newest first)
        runs.sort(key=lambda x: x.get('start_time', ''), reverse=True)
        return runs

    def delete_test_run(self, run_id: str) -> None:
        """
        Delete a test run and all its data.

        Args:
            run_id: Test run identifier
        """
        run_dir = self.base_path / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)

    def _find_test_result_file(self, result_id: str) -> Optional[Path]:
        """
        Find the file containing a specific test result.

        Args:
            result_id: Test result identifier

        Returns:
            Path to result file or None if not found
        """
        # Search through all run directories to find the result file
        for run_dir in self.base_path.iterdir():
            if not run_dir.is_dir():
                continue

            results_dir = run_dir / "test_results"
            if not results_dir.exists():
                continue

            result_file = results_dir / f"{result_id}.json"
            if result_file.exists():
                return result_file

        return None

    def backup_test_run(self, run_id: str, backup_path: Path) -> None:
        """
        Create a backup of a test run.

        Args:
            run_id: Test run identifier
            backup_path: Path where backup should be created
        """
        run_dir = self.base_path / run_id
        if not run_dir.exists():
            raise ValueError(f"Test run {run_id} not found")

        backup_dir = backup_path / run_id
        shutil.copytree(run_dir, backup_dir)

    def export_measurements_csv(self, run_id: str, output_file: Path) -> None:
        """
        Export all measurements for a test run to a single CSV file.

        Args:
            run_id: Test run identifier
            output_file: Output CSV file path
        """
        test_results = self.get_test_results(run_id)

        with open(output_file, 'w') as f:
            f.write("test_name,measurement_name,value,unit,passed,min_limit,max_limit,timestamp\n")

            for result in test_results:
                test_name = result.get("test_name", "")
                for measurement in result.get("measurements", []):
                    limits = measurement.get("limits") or {}
                    min_limit = limits.get("min", "")
                    max_limit = limits.get("max", "")

                    f.write(f"{test_name},{measurement['name']},{measurement['value']},"
                           f"{measurement['unit']},{measurement['passed']},{min_limit},"
                           f"{max_limit},{measurement['timestamp']}\n")