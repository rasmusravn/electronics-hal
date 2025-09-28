"""
Test scenario recording system.

This module provides functionality to record test scenarios in real-time,
capturing instrument interactions, commands, and results for later playback.
"""

import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hal.logging_config import get_logger
from .models import ActionType, TestScenario, TestStep, ValidationRule


class RecordingSession:
    """Manages a single test scenario recording session."""

    def __init__(self, scenario_name: str, description: Optional[str] = None,
                 created_by: str = "user"):
        """Initialize recording session."""
        self.scenario_id = str(uuid.uuid4())
        self.scenario_name = scenario_name
        self.description = description
        self.created_by = created_by
        self.logger = get_logger(__name__)

        self.scenario = TestScenario(
            scenario_id=self.scenario_id,
            name=scenario_name,
            description=description,
            created_by=created_by
        )

        self.is_recording = False
        self.start_time = None
        self.current_step_start = None

        self.logger.info(f"Created recording session: {scenario_name}")

    def start_recording(self) -> None:
        """Start recording test scenario."""
        if self.is_recording:
            self.logger.warning("Recording already in progress")
            return

        self.is_recording = True
        self.start_time = time.time()
        self.logger.info(f"Started recording scenario: {self.scenario_name}")

        # Record start step
        self.record_step(
            action_type=ActionType.START_TEST,
            command="start_recording",
            metadata={"scenario_name": self.scenario_name}
        )

    def stop_recording(self) -> TestScenario:
        """Stop recording and finalize scenario."""
        if not self.is_recording:
            self.logger.warning("No recording in progress")
            return self.scenario

        # Record end step
        self.record_step(
            action_type=ActionType.END_TEST,
            command="stop_recording",
            metadata={"scenario_name": self.scenario_name}
        )

        self.is_recording = False
        end_time = time.time()

        if self.start_time:
            self.scenario.total_duration_ms = (end_time - self.start_time) * 1000

        self.scenario.success_rate = self.scenario.get_success_rate()
        self.logger.info(f"Stopped recording scenario: {self.scenario_name}")

        return self.scenario

    def record_step(self, action_type: ActionType, command: Optional[str] = None,
                   instrument_id: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None,
                   result: Optional[Any] = None, success: bool = True,
                   error_message: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        """Record a single test step."""
        if not self.is_recording and action_type not in [ActionType.START_TEST, ActionType.END_TEST]:
            self.logger.warning(f"Cannot record step {action_type} - recording not active")
            return ""

        step_id = str(uuid.uuid4())
        current_time = time.time()

        # Calculate duration if we have a previous step
        duration_ms = None
        if self.current_step_start:
            duration_ms = (current_time - self.current_step_start) * 1000

        step = TestStep(
            step_id=step_id,
            action_type=action_type,
            instrument_id=instrument_id,
            command=command,
            parameters=parameters or {},
            actual_result=result,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message,
            metadata=metadata or {}
        )

        self.scenario.add_step(step)
        self.current_step_start = current_time

        self.logger.debug(f"Recorded step: {action_type} ({step_id})")
        return step_id

    def add_validation_to_last_step(self, name: str, parameter: str, operator: str,
                                   expected_value: Any, tolerance: Optional[float] = None) -> None:
        """Add validation rule to the most recent step."""
        if not self.scenario.steps:
            self.logger.warning("No steps to add validation to")
            return

        last_step = self.scenario.steps[-1]
        last_step.add_validation(name, parameter, operator, expected_value, tolerance)
        self.logger.debug(f"Added validation to step {last_step.step_id}: {name}")

    def add_global_validation(self, name: str, parameter: str, operator: str,
                            expected_value: Any, tolerance: Optional[float] = None) -> None:
        """Add global validation rule to scenario."""
        validation = ValidationRule(
            name=name,
            parameter=parameter,
            operator=operator,
            expected_value=expected_value,
            tolerance=tolerance
        )
        self.scenario.global_validations.append(validation)
        self.logger.debug(f"Added global validation: {name}")

    def set_instrument_requirement(self, instrument_id: str) -> None:
        """Mark instrument as required for this scenario."""
        if instrument_id not in self.scenario.instruments_required:
            self.scenario.instruments_required.append(instrument_id)
            self.logger.debug(f"Added instrument requirement: {instrument_id}")

    def add_tag(self, tag: str) -> None:
        """Add tag to scenario."""
        if tag not in self.scenario.tags:
            self.scenario.tags.append(tag)
            self.logger.debug(f"Added tag: {tag}")

    def set_environment_variable(self, name: str, value: str) -> None:
        """Set environment variable for scenario."""
        self.scenario.environment_variables[name] = value
        self.logger.debug(f"Set environment variable: {name}={value}")

    def get_current_scenario(self) -> TestScenario:
        """Get current scenario state."""
        return self.scenario


class ScenarioRecorder:
    """High-level test scenario recorder with automatic instrumentation."""

    def __init__(self, storage_dir: Path):
        """Initialize scenario recorder."""
        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)

        self.active_session: Optional[RecordingSession] = None
        self.recorded_scenarios: List[TestScenario] = []

        self.logger.info(f"Initialized scenario recorder with storage: {storage_dir}")

    def start_recording(self, scenario_name: str, description: Optional[str] = None,
                       created_by: str = "user") -> RecordingSession:
        """Start recording a new test scenario."""
        if self.active_session and self.active_session.is_recording:
            self.logger.warning("Stopping previous recording session")
            self.stop_recording()

        self.active_session = RecordingSession(scenario_name, description, created_by)
        self.active_session.start_recording()

        return self.active_session

    def stop_recording(self) -> Optional[TestScenario]:
        """Stop current recording session."""
        if not self.active_session:
            self.logger.warning("No active recording session")
            return None

        scenario = self.active_session.stop_recording()
        self.recorded_scenarios.append(scenario)

        # Save scenario to file
        self.save_scenario(scenario)

        self.active_session = None
        return scenario

    def record_instrument_connect(self, instrument_id: str, address: str,
                                success: bool = True, error_message: Optional[str] = None) -> None:
        """Record instrument connection."""
        if not self.active_session:
            return

        self.active_session.record_step(
            action_type=ActionType.CONNECT,
            instrument_id=instrument_id,
            command="connect",
            parameters={"address": address},
            success=success,
            error_message=error_message
        )

        if success:
            self.active_session.set_instrument_requirement(instrument_id)

    def record_instrument_disconnect(self, instrument_id: str) -> None:
        """Record instrument disconnection."""
        if not self.active_session:
            return

        self.active_session.record_step(
            action_type=ActionType.DISCONNECT,
            instrument_id=instrument_id,
            command="disconnect",
            success=True
        )

    def record_configuration(self, instrument_id: str, config: Dict[str, Any]) -> None:
        """Record instrument configuration."""
        if not self.active_session:
            return

        self.active_session.record_step(
            action_type=ActionType.CONFIGURE,
            instrument_id=instrument_id,
            command="configure",
            parameters=config,
            success=True
        )

    def record_measurement(self, instrument_id: str, measurement_name: str,
                         value: Any, unit: Optional[str] = None,
                         success: bool = True, error_message: Optional[str] = None) -> None:
        """Record measurement operation."""
        if not self.active_session:
            return

        parameters = {"measurement": measurement_name}
        if unit:
            parameters["unit"] = unit

        step_id = self.active_session.record_step(
            action_type=ActionType.MEASURE,
            instrument_id=instrument_id,
            command="measure",
            parameters=parameters,
            result=value,
            success=success,
            error_message=error_message
        )

        return step_id

    def record_validation(self, name: str, parameter: str, operator: str,
                        expected_value: Any, tolerance: Optional[float] = None) -> None:
        """Record validation rule for last measurement."""
        if not self.active_session:
            return

        self.active_session.add_validation_to_last_step(
            name, parameter, operator, expected_value, tolerance
        )

    def record_wait(self, duration_seconds: float, reason: Optional[str] = None) -> None:
        """Record wait/delay operation."""
        if not self.active_session:
            return

        time.sleep(duration_seconds)

        self.active_session.record_step(
            action_type=ActionType.WAIT,
            command="wait",
            parameters={
                "duration_seconds": duration_seconds,
                "reason": reason or "Timed delay"
            },
            success=True
        )

    def record_log_message(self, message: str, level: str = "INFO") -> None:
        """Record log message."""
        if not self.active_session:
            return

        self.active_session.record_step(
            action_type=ActionType.LOG,
            command="log",
            parameters={
                "message": message,
                "level": level
            },
            success=True
        )

    def save_scenario(self, scenario: TestScenario) -> Path:
        """Save scenario to storage."""
        filename = f"{scenario.scenario_id}_{scenario.name.replace(' ', '_')}.json"
        file_path = self.storage_dir / filename

        scenario.save_to_file(file_path)
        self.logger.info(f"Saved scenario to: {file_path}")

        return file_path

    def load_scenario(self, file_path: Path) -> TestScenario:
        """Load scenario from file."""
        scenario = TestScenario.load_from_file(file_path)
        self.logger.info(f"Loaded scenario: {scenario.name}")
        return scenario

    def list_scenarios(self) -> List[Dict[str, Any]]:
        """List all available scenarios."""
        scenarios = []

        for file_path in self.storage_dir.glob("*.json"):
            try:
                scenario = self.load_scenario(file_path)
                scenarios.append({
                    "file_path": str(file_path),
                    "summary": scenario.get_summary()
                })
            except Exception as e:
                self.logger.error(f"Failed to load scenario {file_path}: {e}")

        return scenarios

    def get_recording_status(self) -> Dict[str, Any]:
        """Get current recording status."""
        if not self.active_session:
            return {
                "recording": False,
                "session": None
            }

        return {
            "recording": self.active_session.is_recording,
            "session": {
                "scenario_id": self.active_session.scenario_id,
                "scenario_name": self.active_session.scenario_name,
                "steps_recorded": len(self.active_session.scenario.steps),
                "start_time": self.active_session.start_time
            }
        }

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self.active_session is not None and self.active_session.is_recording