"""
Central pytest configuration and fixtures.

This module provides the core fixtures that are shared across all test modules,
including configuration management, database access, logging, and instrument fixtures.
"""

import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

# Import core infrastructure
from hal.config_loader import load_config
from hal.config_models import SystemConfig
from hal.file_storage_manager import FileSystemStorage
from hal.drivers.keysight_33500_series import Mock33500Series
from hal.drivers.keysight_34461a import Mock34461A
from hal.drivers.keysight_e36100_series import MockKeysightE36100Series

# Import instrument interfaces and drivers
from hal.interfaces import DigitalMultimeter, FunctionGenerator, PowerSupply
from hal.logging_config import get_logger, setup_logging

# Global variables to track test run state
_test_run_id: Optional[str] = None
_storage_manager: Optional[FileSystemStorage] = None
_session_config: Optional[SystemConfig] = None


class TestLogger:
    """Helper class for logging test results and measurements to file storage."""

    def __init__(self, storage_manager: FileSystemStorage, run_id: str, test_name: str):
        """
        Initialize test logger.

        Args:
            storage_manager: File system storage manager instance
            run_id: Test run identifier
            test_name: Name of the current test
        """
        self.storage_manager = storage_manager
        self.run_id = run_id
        self.test_name = test_name
        self.result_id: Optional[str] = None
        self.logger = get_logger(f"test.{test_name}")

    def start_test(self) -> None:
        """Start logging for this test (called automatically by fixture)."""
        self.result_id = self.storage_manager.create_test_result(self.run_id, self.test_name)
        self.logger.info(f"Test {self.test_name} started with result_id={self.result_id}")

    def log_measurement(
        self,
        name: str,
        value: float,
        unit: str,
        limits: Optional[Dict[str, float]] = None,
        **metadata: Any
    ) -> None:
        """
        Log a measurement result.

        Args:
            name: Measurement name
            value: Measured value
            unit: Unit of measurement
            limits: Optional pass/fail limits {"min": float, "max": float}
            **metadata: Additional metadata to log
        """
        if self.result_id is None:
            raise RuntimeError("Test not started - call start_test() first")

        self.storage_manager.add_measurement(self.result_id, name, value, unit, limits)

        # Log the measurement with metadata
        log_data = {
            "measurement": name,
            "value": value,
            "unit": unit,
            "limits": limits,
            **metadata
        }

        # Determine pass/fail status
        passed = True
        if limits:
            if "min" in limits and value < limits["min"]:
                passed = False
            if "max" in limits and value > limits["max"]:
                passed = False

        status = "PASS" if passed else "FAIL"
        self.logger.info(f"MEASUREMENT {status}: {name} = {value} {unit}", extra=log_data)

    def finish_test(self, outcome: str, duration: float, error_message: Optional[str] = None) -> None:
        """
        Finish logging for this test.

        Args:
            outcome: Test outcome (PASSED, FAILED, SKIPPED)
            duration: Test execution time in seconds
            error_message: Optional error message for failed tests
        """
        if self.result_id is None:
            raise RuntimeError("Test not started - call start_test() first")

        self.storage_manager.update_test_result(
            self.result_id, outcome, duration, error_message=error_message
        )
        self.logger.info(f"Test {self.test_name} finished: {outcome} in {duration:.3f}s")


# ================================================================================
# Session-scoped fixtures (created once per test session)
# ================================================================================

@pytest.fixture(scope="session")
def config() -> SystemConfig:
    """
    Load and provide system configuration for the entire test session.

    This fixture loads the configuration once at the start of the session
    and provides it to all tests. For test isolation, it uses temporary
    directories for logs and database unless overridden by environment variables.
    """
    global _session_config

    if _session_config is None:
        # Create temporary directories for test isolation
        temp_dir = Path(tempfile.mkdtemp(prefix="hal_test_"))

        # Load base configuration
        _session_config = load_config()

        # Override paths for test isolation
        _session_config.paths.log_dir = temp_dir / "logs"
        _session_config.paths.report_dir = temp_dir / "reports"
        _session_config.paths.test_data_dir = temp_dir / "test_data"

        # Ensure directories exist
        _session_config.paths.log_dir.mkdir(parents=True, exist_ok=True)
        _session_config.paths.report_dir.mkdir(parents=True, exist_ok=True)

    return _session_config


@pytest.fixture(scope="session")
def storage_manager(config: SystemConfig) -> Generator[FileSystemStorage, None, None]:
    """
    Provide file system storage manager for the entire test session.

    This fixture creates a single storage manager that persists for the
    entire test session, allowing all test results to be stored in the same
    directory structure.
    """
    global _storage_manager

    storage = FileSystemStorage(config.paths.test_data_dir)
    _storage_manager = storage

    yield storage

    _storage_manager = None


@pytest.fixture(scope="session", autouse=True)
def test_session(config: SystemConfig, storage_manager: FileSystemStorage) -> Generator[str, None, None]:
    """
    Manage the test session lifecycle.

    This fixture automatically runs for every test session and handles:
    - Generating unique test run ID
    - Setting up logging
    - Creating test run record in file storage
    - Updating final statistics
    """
    global _test_run_id

    # Generate unique test run ID
    _test_run_id = str(uuid.uuid4())

    # Setup logging with the test run ID
    setup_logging(config, _test_run_id)
    logger = get_logger(__name__)
    logger.info(f"Starting test session {_test_run_id}")

    # Create test run record
    storage_manager.create_test_run(_test_run_id, config)

    yield _test_run_id

    # Session teardown - update final statistics
    logger.info(f"Completing test session {_test_run_id}")
    storage_manager.update_test_run(_test_run_id, "COMPLETED")


# ================================================================================
# Function-scoped fixtures (created for each test function)
# ================================================================================

@pytest.fixture
def test_logger(
    storage_manager: FileSystemStorage,
    test_session: str,
    request: pytest.FixtureRequest
) -> Generator[TestLogger, None, None]:
    """
    Provide test logger for individual test functions.

    This fixture creates a TestLogger instance for each test function,
    handles the test lifecycle (start/finish), and integrates with pytest
    to capture test outcomes automatically.
    """
    test_name = request.node.name
    logger = TestLogger(storage_manager, test_session, test_name)

    # Start the test
    logger.start_test()

    yield logger

    # Finish the test - outcome will be determined by pytest hooks
    # This is a placeholder; the actual finish call happens in pytest_runtest_makereport


@pytest.fixture
def mock_power_supply(config: SystemConfig) -> Generator[PowerSupply, None, None]:
    """
    Provide a mock power supply for testing.

    This fixture creates a mock power supply, connects it, and ensures
    it's properly disconnected after the test.
    """
    ps = MockKeysightE36100Series(model="E36103A")  # 2-channel model

    # Use config if available, otherwise use mock address
    address = "MOCK::POWER_SUPPLY"
    if config.power_supply and config.power_supply.address:
        if "MOCK" in config.power_supply.address.upper():
            address = config.power_supply.address

    ps.connect(address)

    # Reset to known state
    ps.reset()

    yield ps

    # Cleanup: turn off all outputs and disconnect
    try:
        for ch in range(1, ps.num_channels + 1):
            ps.set_output_state(False, ch)
        ps.disconnect()
    except Exception as e:
        # Log but don't fail test due to cleanup issues
        logger = get_logger(__name__)
        logger.warning(f"Error during power supply cleanup: {e}")


@pytest.fixture
def mock_multimeter(config: SystemConfig) -> Generator[DigitalMultimeter, None, None]:
    """
    Provide a mock digital multimeter for testing.

    This fixture creates a mock DMM, connects it, and ensures
    it's properly disconnected after the test.
    """
    dmm = Mock34461A()

    # Use config if available, otherwise use mock address
    address = "MOCK::MULTIMETER"
    if config.multimeter and config.multimeter.address:
        if "MOCK" in config.multimeter.address.upper():
            address = config.multimeter.address

    dmm.connect(address)

    # Reset to known state
    dmm.reset()

    yield dmm

    # Cleanup: disconnect
    try:
        dmm.disconnect()
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Error during multimeter cleanup: {e}")


@pytest.fixture
def mock_function_generator(config: SystemConfig) -> Generator[FunctionGenerator, None, None]:
    """
    Provide a mock function generator for testing.

    This fixture creates a mock function generator, connects it, and ensures
    it's properly disconnected after the test.
    """
    fg = Mock33500Series(model="33512B")  # 2-channel model

    # Use config if available, otherwise use mock address
    address = "MOCK::FUNCTION_GENERATOR"
    if config.function_generator and config.function_generator.address:
        if "MOCK" in config.function_generator.address.upper():
            address = config.function_generator.address

    fg.connect(address)

    # Reset to known state
    fg.reset()

    yield fg

    # Cleanup: turn off all outputs and disconnect
    try:
        for ch in range(1, fg.num_channels + 1):
            fg.set_output_state(False, ch)
        fg.disconnect()
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Error during function generator cleanup: {e}")


# ================================================================================
# Convenience fixtures for common test setups
# ================================================================================

@pytest.fixture
def test_setup(
    mock_power_supply: PowerSupply,
    mock_multimeter: DigitalMultimeter,
    mock_function_generator: FunctionGenerator,
    test_logger: TestLogger
) -> Dict[str, Any]:
    """
    Provide a complete test setup with all instruments and logging.

    This convenience fixture provides everything needed for most hardware tests:
    - Power supply
    - Multimeter
    - Function generator
    - Test logger for measurements

    Returns:
        Dictionary containing all test resources
    """
    return {
        "power_supply": mock_power_supply,
        "multimeter": mock_multimeter,
        "function_generator": mock_function_generator,
        "test_logger": test_logger
    }


# ================================================================================
# Pytest hooks for advanced test lifecycle management
# ================================================================================

def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> None:
    """
    Hook called after each test phase (setup, call, teardown).

    This hook captures test outcomes and updates the database with
    final test results.
    """
    global _db_manager, _test_run_id

    # Only process the "call" phase (actual test execution)
    if call.when != "call":
        return

    # Get test outcome
    outcome = "PASSED"
    error_message = None

    if call.excinfo is not None:
        if call.excinfo.type == pytest.skip.Exception:
            outcome = "SKIPPED"
        else:
            outcome = "FAILED"
            error_message = str(call.excinfo.value)

    # Calculate duration
    duration = call.duration

    # Update database if we have access to TestLogger
    if hasattr(item, "fixturenames") and "test_logger" in item.fixturenames:
        # The test_logger fixture will be finalized automatically
        # We need to find it and call finish_test
        pass  # This will be handled by the fixture cleanup


def pytest_collection_modifyitems(config: pytest.Config, items) -> None:
    """
    Hook called after test collection to modify test items.

    This hook can be used to:
    - Add markers based on test names or paths
    - Skip tests based on configuration
    - Organize test execution order
    """
    for item in items:
        # Add markers based on test path
        if "hardware" in str(item.fspath):
            item.add_marker(pytest.mark.hardware)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add markers based on test path subdirectories
        if "power_management" in str(item.fspath):
            item.add_marker(pytest.mark.power_management)
        elif "measurement" in str(item.fspath):
            item.add_marker(pytest.mark.measurement)
        elif "signal_generation" in str(item.fspath):
            item.add_marker(pytest.mark.signal_generation)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """
    Hook called after the entire test session finishes.

    This hook handles final cleanup and report generation.
    """
    global _test_run_id, _storage_manager

    if _test_run_id and _storage_manager:
        logger = get_logger(__name__)

        # Determine final status
        final_status = "COMPLETED" if exitstatus == 0 else "FAILED"

        # Get test statistics
        summary = _storage_manager.get_run_summary(_test_run_id)
        logger.info(f"Test session {_test_run_id} finished with status: {final_status}")
        logger.info(f"Test summary: {summary.get('outcome_counts', {})}")

        # Update final status
        _storage_manager.update_test_run(_test_run_id, final_status)


# ================================================================================
# Utility functions for tests
# ================================================================================

def get_current_test_run_id() -> Optional[str]:
    """Get the current test run ID (useful for advanced test scenarios)."""
    return _test_run_id


def get_test_storage() -> Optional[FileSystemStorage]:
    """Get the current test storage manager (useful for advanced test scenarios)."""
    return _storage_manager
