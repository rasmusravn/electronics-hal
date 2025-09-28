"""Database management for test results and measurements."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config_models import SystemConfig


class DatabaseManager:
    """Manages SQLite database operations for test results."""

    def __init__(self, db_path: Path):
        """
        Initialize database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Establish connection to the database."""
        self._connection = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._connection.row_factory = sqlite3.Row  # Enable dict-like access
        self._initialize_database()

    def disconnect(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    def _initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()

        # Create TestRuns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TestRuns (
                run_id TEXT PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'IN_PROGRESS',
                configuration_snapshot TEXT NOT NULL,
                total_tests INTEGER DEFAULT 0,
                passed_tests INTEGER DEFAULT 0,
                failed_tests INTEGER DEFAULT 0,
                skipped_tests INTEGER DEFAULT 0
            )
        """)

        # Create TestResults table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TestResults (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                outcome TEXT NOT NULL,
                start_time TIMESTAMP NOT NULL,
                duration REAL NOT NULL,
                logs TEXT,
                error_message TEXT,
                FOREIGN KEY (run_id) REFERENCES TestRuns (run_id)
            )
        """)

        # Create Measurements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Measurements (
                measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                limits TEXT,
                timestamp TIMESTAMP NOT NULL,
                passed BOOLEAN NOT NULL,
                FOREIGN KEY (result_id) REFERENCES TestResults (result_id)
            )
        """)

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_run_id ON TestResults (run_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_measurements_result_id ON Measurements (result_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_test_results_outcome ON TestResults (outcome)")

        self._connection.commit()

    def create_test_run(self, run_id: str, config: SystemConfig) -> None:
        """
        Create a new test run record.

        Args:
            run_id: Unique identifier for the test run
            config: System configuration snapshot
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute("""
            INSERT INTO TestRuns (run_id, start_time, configuration_snapshot)
            VALUES (?, ?, ?)
        """, (
            run_id,
            datetime.now(),
            config.model_dump_json()
        ))
        self._connection.commit()

    def update_test_run(self, run_id: str, status: str, **kwargs: Any) -> None:
        """
        Update a test run record.

        Args:
            run_id: Test run identifier
            status: Final status of the test run
            **kwargs: Additional fields to update
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        # Build dynamic update query
        fields = ["status = ?", "end_time = ?"]
        values = [status, datetime.now()]

        for key, value in kwargs.items():
            if key in ["total_tests", "passed_tests", "failed_tests", "skipped_tests"]:
                fields.append(f"{key} = ?")
                values.append(value)

        values.append(run_id)  # For WHERE clause

        cursor = self._connection.cursor()
        cursor.execute(f"""
            UPDATE TestRuns SET {', '.join(fields)}
            WHERE run_id = ?
        """, values)
        self._connection.commit()

    def create_test_result(self, run_id: str, test_name: str) -> int:
        """
        Create a new test result record.

        Args:
            run_id: Test run identifier
            test_name: Name of the test

        Returns:
            result_id: Primary key of the created record
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute("""
            INSERT INTO TestResults (run_id, test_name, outcome, start_time, duration)
            VALUES (?, ?, 'RUNNING', ?, 0)
        """, (run_id, test_name, datetime.now()))
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to create test result")
        return cursor.lastrowid

    def update_test_result(
        self,
        result_id: int,
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
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute("""
            UPDATE TestResults
            SET outcome = ?, duration = ?, logs = ?, error_message = ?
            WHERE result_id = ?
        """, (outcome, duration, logs, error_message, result_id))
        self._connection.commit()

    def add_measurement(
        self,
        result_id: int,
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
        if not self._connection:
            raise RuntimeError("Database not connected")

        # Check if measurement passes limits
        passed = True
        if limits:
            if "min" in limits and value < limits["min"]:
                passed = False
            if "max" in limits and value > limits["max"]:
                passed = False

        cursor = self._connection.cursor()
        cursor.execute("""
            INSERT INTO Measurements (result_id, name, value, unit, limits, timestamp, passed)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            result_id,
            name,
            value,
            unit,
            json.dumps(limits) if limits else None,
            datetime.now(),
            passed
        ))
        self._connection.commit()

    def get_test_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Get test run information.

        Args:
            run_id: Test run identifier

        Returns:
            Test run data or None if not found
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute("SELECT * FROM TestRuns WHERE run_id = ?", (run_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_test_results(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Get all test results for a run.

        Args:
            run_id: Test run identifier

        Returns:
            List of test result records
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute("SELECT * FROM TestResults WHERE run_id = ? ORDER BY start_time", (run_id,))
        return [dict(row) for row in cursor.fetchall()]

    def get_measurements(self, result_id: int) -> List[Dict[str, Any]]:
        """
        Get all measurements for a test result.

        Args:
            result_id: Test result identifier

        Returns:
            List of measurement records
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()
        cursor.execute(
            "SELECT * FROM Measurements WHERE result_id = ? ORDER BY timestamp",
            (result_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_run_summary(self, run_id: str) -> Dict[str, Any]:
        """
        Get summary statistics for a test run.

        Args:
            run_id: Test run identifier

        Returns:
            Summary statistics dictionary
        """
        if not self._connection:
            raise RuntimeError("Database not connected")

        cursor = self._connection.cursor()

        # Get test run info
        run_info = self.get_test_run(run_id)
        if not run_info:
            return {}

        # Get test counts by outcome
        cursor.execute("""
            SELECT outcome, COUNT(*) as count
            FROM TestResults
            WHERE run_id = ?
            GROUP BY outcome
        """, (run_id,))
        outcome_counts = {row["outcome"]: row["count"] for row in cursor.fetchall()}

        # Get failed measurements count
        cursor.execute("""
            SELECT COUNT(*) as failed_measurements
            FROM Measurements m
            JOIN TestResults r ON m.result_id = r.result_id
            WHERE r.run_id = ? AND m.passed = 0
        """, (run_id,))
        failed_measurements = cursor.fetchone()["failed_measurements"]

        return {
            **run_info,
            "outcome_counts": outcome_counts,
            "failed_measurements": failed_measurements
        }
