"""
Test scenario playback system.

This module provides functionality to play back recorded test scenarios,
executing steps and validating results for regression testing.
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from hal.logging_config import get_logger
from .models import ActionType, TestScenario, TestStep, ValidationRule


class PlaybackResult:
    """Result of scenario playback execution."""

    def __init__(self, scenario: TestScenario):
        self.scenario = scenario
        self.start_time = datetime.utcnow()
        self.end_time: Optional[datetime] = None
        self.success = True
        self.steps_executed = 0
        self.steps_passed = 0
        self.steps_failed = 0
        self.validation_results: List[Dict[str, Any]] = []
        self.error_messages: List[str] = []

    def finish(self) -> None:
        """Mark playback as finished."""
        self.end_time = datetime.utcnow()

    def add_step_result(self, step: TestStep, success: bool,
                       validation_results: List[Dict[str, Any]] = None,
                       error_message: Optional[str] = None) -> None:
        """Add result for executed step."""
        self.steps_executed += 1

        if success:
            self.steps_passed += 1
        else:
            self.steps_failed += 1
            self.success = False
            if error_message:
                self.error_messages.append(f"Step {step.step_id}: {error_message}")

        if validation_results:
            self.validation_results.extend(validation_results)

    def get_summary(self) -> Dict[str, Any]:
        """Get playback summary."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "scenario_id": self.scenario.scenario_id,
            "scenario_name": self.scenario.name,
            "success": self.success,
            "steps_executed": self.steps_executed,
            "steps_passed": self.steps_passed,
            "steps_failed": self.steps_failed,
            "success_rate": (self.steps_passed / max(1, self.steps_executed)) * 100,
            "validation_results": len(self.validation_results),
            "validations_passed": sum(1 for v in self.validation_results if v.get("passed", False)),
            "duration_seconds": duration,
            "error_count": len(self.error_messages),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None
        }


class PlaybackSession:
    """Manages playback of a single test scenario."""

    def __init__(self, scenario: TestScenario, instrument_manager: Any = None):
        """Initialize playback session."""
        self.scenario = scenario
        self.instrument_manager = instrument_manager
        self.logger = get_logger(__name__)
        self.result = PlaybackResult(scenario)

        # Execution context
        self.variables: Dict[str, Any] = {}
        self.step_handlers: Dict[ActionType, Callable] = {
            ActionType.CONNECT: self._handle_connect,
            ActionType.DISCONNECT: self._handle_disconnect,
            ActionType.CONFIGURE: self._handle_configure,
            ActionType.MEASURE: self._handle_measure,
            ActionType.SET_OUTPUT: self._handle_set_output,
            ActionType.GET_STATUS: self._handle_get_status,
            ActionType.WAIT: self._handle_wait,
            ActionType.LOG: self._handle_log,
            ActionType.VALIDATE: self._handle_validate,
            ActionType.START_TEST: self._handle_start_test,
            ActionType.END_TEST: self._handle_end_test
        }

        self.dry_run = False
        self.continue_on_error = True

    def set_dry_run(self, enabled: bool) -> None:
        """Enable/disable dry run mode (simulation only)."""
        self.dry_run = enabled

    def set_continue_on_error(self, enabled: bool) -> None:
        """Enable/disable continuing on errors."""
        self.continue_on_error = enabled

    def set_variable(self, name: str, value: Any) -> None:
        """Set variable for playback context."""
        self.variables[name] = value

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get variable from playback context."""
        return self.variables.get(name, default)

    def execute(self) -> PlaybackResult:
        """Execute the scenario playback."""
        self.logger.info(f"Starting playback of scenario: {self.scenario.name}")

        if self.dry_run:
            self.logger.info("Dry run mode enabled - simulating execution")

        # Validate requirements
        missing_instruments = []
        if self.instrument_manager:
            available_instruments = getattr(self.instrument_manager, 'get_available_instruments', lambda: [])()
            missing_instruments = self.scenario.validate_requirements(available_instruments)

        if missing_instruments:
            error_msg = f"Missing required instruments: {missing_instruments}"
            self.logger.error(error_msg)
            self.result.error_messages.append(error_msg)
            self.result.success = False
            self.result.finish()
            return self.result

        # Execute steps
        for step in self.scenario.steps:
            try:
                self._execute_step(step)

                if not self.continue_on_error and not self.result.success:
                    self.logger.warning("Stopping playback due to error (continue_on_error=False)")
                    break

            except Exception as e:
                error_msg = f"Unexpected error executing step {step.step_id}: {e}"
                self.logger.error(error_msg)
                self.result.add_step_result(step, False, error_message=error_msg)

                if not self.continue_on_error:
                    break

        # Execute global validations
        self._execute_global_validations()

        self.result.finish()
        self.logger.info(f"Playback completed: {self.result.get_summary()}")

        return self.result

    def _execute_step(self, step: TestStep) -> None:
        """Execute a single test step."""
        self.logger.debug(f"Executing step {step.step_id}: {step.action_type}")

        start_time = time.time()
        success = True
        error_message = None
        validation_results = []

        try:
            # Get handler for action type
            handler = self.step_handlers.get(step.action_type)
            if not handler:
                error_message = f"No handler for action type: {step.action_type}"
                success = False
            else:
                # Execute step handler
                result = handler(step)

                # Validate results if step has validations
                if step.validations and result is not None:
                    validation_results = step.validate_result(result)

                    # Check if all validations passed
                    failed_validations = [v for v in validation_results if not v["passed"]]
                    if failed_validations:
                        success = False
                        error_message = f"Validation failures: {[v['rule_name'] for v in failed_validations]}"

        except Exception as e:
            success = False
            error_message = str(e)

        execution_time = (time.time() - start_time) * 1000
        self.logger.debug(f"Step {step.step_id} completed in {execution_time:.1f}ms")

        self.result.add_step_result(step, success, validation_results, error_message)

    def _execute_global_validations(self) -> None:
        """Execute global validation rules."""
        if not self.scenario.global_validations:
            return

        self.logger.debug("Executing global validations")

        for validation in self.scenario.global_validations:
            try:
                # Global validations need context - for now, just log them
                self.logger.info(f"Global validation: {validation.get_description()}")

            except Exception as e:
                self.logger.error(f"Error in global validation {validation.name}: {e}")

    # Step handlers

    def _handle_connect(self, step: TestStep) -> Any:
        """Handle instrument connection step."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Connect to {step.instrument_id}")
            return True

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for connection")

        address = step.parameters.get("address")
        if not address:
            raise ValueError("Connection step missing address parameter")

        # Attempt connection
        result = getattr(self.instrument_manager, 'connect_instrument', lambda x, y: True)(
            step.instrument_id, address
        )

        return result

    def _handle_disconnect(self, step: TestStep) -> Any:
        """Handle instrument disconnection step."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Disconnect from {step.instrument_id}")
            return True

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for disconnection")

        result = getattr(self.instrument_manager, 'disconnect_instrument', lambda x: True)(
            step.instrument_id
        )

        return result

    def _handle_configure(self, step: TestStep) -> Any:
        """Handle instrument configuration step."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Configure {step.instrument_id}: {step.parameters}")
            return True

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for configuration")

        # Apply configuration parameters
        result = getattr(self.instrument_manager, 'configure_instrument', lambda x, y: True)(
            step.instrument_id, step.parameters
        )

        return result

    def _handle_measure(self, step: TestStep) -> Any:
        """Handle measurement step."""
        if self.dry_run:
            # Return simulated value based on expected result
            self.logger.info(f"[DRY RUN] Measure {step.parameters.get('measurement', 'value')} from {step.instrument_id}")
            return step.expected_result or 1.23

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for measurement")

        measurement_name = step.parameters.get("measurement")
        if not measurement_name:
            raise ValueError("Measurement step missing measurement parameter")

        result = getattr(self.instrument_manager, 'measure', lambda x, y: 1.23)(
            step.instrument_id, measurement_name
        )

        return result

    def _handle_set_output(self, step: TestStep) -> Any:
        """Handle output setting step."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Set output on {step.instrument_id}: {step.parameters}")
            return True

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for output setting")

        result = getattr(self.instrument_manager, 'set_output', lambda x, y: True)(
            step.instrument_id, step.parameters
        )

        return result

    def _handle_get_status(self, step: TestStep) -> Any:
        """Handle status query step."""
        if self.dry_run:
            self.logger.info(f"[DRY RUN] Get status from {step.instrument_id}")
            return {"status": "ok", "connected": True}

        if not self.instrument_manager:
            raise RuntimeError("No instrument manager available for status query")

        result = getattr(self.instrument_manager, 'get_status', lambda x: {"status": "ok"})(
            step.instrument_id
        )

        return result

    def _handle_wait(self, step: TestStep) -> Any:
        """Handle wait/delay step."""
        duration = step.parameters.get("duration_seconds", 1.0)
        reason = step.parameters.get("reason", "Timed delay")

        if self.dry_run:
            self.logger.info(f"[DRY RUN] Wait {duration}s: {reason}")
        else:
            self.logger.info(f"Waiting {duration}s: {reason}")
            time.sleep(duration)

        return True

    def _handle_log(self, step: TestStep) -> Any:
        """Handle log message step."""
        message = step.parameters.get("message", "")
        level = step.parameters.get("level", "INFO")

        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"[PLAYBACK] {message}")

        return True

    def _handle_validate(self, step: TestStep) -> Any:
        """Handle validation step."""
        # Validation is handled automatically for each step
        self.logger.debug(f"Validation step: {step.parameters}")
        return True

    def _handle_start_test(self, step: TestStep) -> Any:
        """Handle test start step."""
        self.logger.info(f"Starting test scenario: {step.parameters.get('scenario_name', 'Unknown')}")
        return True

    def _handle_end_test(self, step: TestStep) -> Any:
        """Handle test end step."""
        self.logger.info(f"Ending test scenario: {step.parameters.get('scenario_name', 'Unknown')}")
        return True


class ScenarioPlayer:
    """High-level scenario player with batch execution capabilities."""

    def __init__(self, storage_dir: Path, instrument_manager: Any = None):
        """Initialize scenario player."""
        self.storage_dir = storage_dir
        self.instrument_manager = instrument_manager
        self.logger = get_logger(__name__)

        self.execution_history: List[PlaybackResult] = []

    def play_scenario_file(self, file_path: Path, dry_run: bool = False,
                          continue_on_error: bool = True) -> PlaybackResult:
        """Play scenario from file."""
        scenario = TestScenario.load_from_file(file_path)
        return self.play_scenario(scenario, dry_run, continue_on_error)

    def play_scenario(self, scenario: TestScenario, dry_run: bool = False,
                     continue_on_error: bool = True) -> PlaybackResult:
        """Play a test scenario."""
        session = PlaybackSession(scenario, self.instrument_manager)
        session.set_dry_run(dry_run)
        session.set_continue_on_error(continue_on_error)

        result = session.execute()
        self.execution_history.append(result)

        return result

    def play_scenarios_batch(self, scenario_files: List[Path], dry_run: bool = False,
                           continue_on_error: bool = True) -> List[PlaybackResult]:
        """Play multiple scenarios in batch."""
        results = []

        for file_path in scenario_files:
            try:
                result = self.play_scenario_file(file_path, dry_run, continue_on_error)
                results.append(result)

                if not result.success and not continue_on_error:
                    self.logger.warning(f"Stopping batch execution due to failure in {file_path}")
                    break

            except Exception as e:
                self.logger.error(f"Failed to execute scenario {file_path}: {e}")

        return results

    def list_available_scenarios(self) -> List[Dict[str, Any]]:
        """List all available scenarios in storage directory."""
        scenarios = []

        for file_path in self.storage_dir.glob("*.json"):
            try:
                scenario = TestScenario.load_from_file(file_path)
                scenarios.append({
                    "file_path": str(file_path),
                    "summary": scenario.get_summary()
                })
            except Exception as e:
                self.logger.error(f"Failed to load scenario {file_path}: {e}")

        return scenarios

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get execution history summaries."""
        return [result.get_summary() for result in self.execution_history]

    def clear_execution_history(self) -> None:
        """Clear execution history."""
        self.execution_history.clear()
        self.logger.info("Cleared execution history")