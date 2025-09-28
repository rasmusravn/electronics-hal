#!/usr/bin/env python3
"""
Integration test for Phase 1 core infrastructure services.

This script validates that the configuration management, database, and logging
systems work together correctly without requiring Pytest or hardware.
"""

import json
import logging
import tempfile
import uuid
from pathlib import Path

from hal.config_loader import load_config, create_example_config, ConfigurationError
from hal.config_models import SystemConfig
from hal.file_storage_manager import FileSystemStorage
from hal.logging_config import setup_logging, get_logger, LogCapture


def test_configuration_management():
    """Test configuration loading and validation."""
    print("Testing configuration management...")

    # Test 1: Load default configuration (should work with empty config)
    try:
        config = load_config(Path("nonexistent.yml"))
        assert isinstance(config, SystemConfig)
        print("✓ Default configuration loaded successfully")
    except Exception as e:
        print(f"✗ Failed to load default configuration: {e}")
        return False

    # Test 2: Create and load example configuration
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yml"
            create_example_config(config_path)

            config = load_config(config_path)
            assert config.power_supply is not None
            assert config.power_supply.address == "USB0::0x0957::0x8C07::MY52200021::INSTR"
            assert config.logging.level == "INFO"
            print("✓ Example configuration created and loaded successfully")
    except Exception as e:
        print(f"✗ Failed to create/load example configuration: {e}")
        return False

    # Test 3: Validate configuration validation (should fail)
    try:
        invalid_config = {"logging": {"level": "INVALID_LEVEL"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            import yaml
            yaml.dump(invalid_config, f)
            f.flush()

            try:
                load_config(Path(f.name))
                print("✗ Configuration validation should have failed")
                return False
            except ConfigurationError:
                print("✓ Configuration validation correctly rejected invalid config")
    except Exception as e:
        print(f"✗ Configuration validation test failed: {e}")
        return False

    return True


def test_file_storage_operations():
    """Test file system storage creation and operations."""
    print("\nTesting file system storage operations...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            storage_path = temp_path / "test_data"
            config = SystemConfig()
            config.paths.test_data_dir = storage_path

            # Test 1: Storage initialization
            storage = FileSystemStorage(storage_path)
            print("✓ File system storage initialized")

            # Test 2: Create test run
            run_id = str(uuid.uuid4())
            run_dir = storage.create_test_run(run_id, config)
            assert run_dir.exists()
            print("✓ Test run created")

            # Test 3: Create test result
            result_id = storage.create_test_result(run_id, "test_example")
            assert isinstance(result_id, str)
            print("✓ Test result created")

            # Test 4: Add measurements
            storage.add_measurement(result_id, "voltage", 5.0, "V", {"min": 4.5, "max": 5.5})
            storage.add_measurement(result_id, "current", 2.0, "A", {"min": 1.0, "max": 3.0})
            print("✓ Measurements added")

            # Test 5: Update test result
            storage.update_test_result(result_id, "PASSED", 1.5)
            print("✓ Test result updated")

            # Test 6: Update test run
            storage.update_test_run(run_id, "COMPLETED", total_tests=1, passed_tests=1)
            print("✓ Test run updated")

            # Test 7: Query data
            run_data = storage.get_test_run(run_id)
            assert run_data is not None
            assert run_data["status"] == "COMPLETED"

            results = storage.get_test_results(run_id)
            assert len(results) == 1
            assert results[0]["outcome"] == "PASSED"

            measurements = storage.get_measurements(result_id)
            assert len(measurements) == 2

            summary = storage.get_run_summary(run_id)
            assert summary["outcome_counts"]["PASSED"] == 1
            print("✓ Data queries successful")

            # Test 8: Check file structure
            assert (run_dir / "metadata.json").exists()
            assert (run_dir / "test_results").exists()
            assert (run_dir / "measurements").exists()
            print("✓ File structure verified")

            print("✓ File storage tests completed successfully")

    except Exception as e:
        print(f"✗ File storage test failed: {e}")
        return False

    return True


def test_logging_system():
    """Test logging configuration and functionality."""
    print("\nTesting logging system...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test 1: Setup logging with custom config
            config = SystemConfig()
            config.paths.log_dir = Path(temp_dir)

            run_id = setup_logging(config)
            assert isinstance(run_id, str)
            print("✓ Logging system initialized")

            # Test 2: Test basic logging
            logger = get_logger(__name__)
            logger.info("Test info message")
            logger.debug("Test debug message")
            logger.warning("Test warning message")
            print("✓ Basic logging operations successful")

            # Test 3: Verify log file creation
            log_files = list(Path(temp_dir).glob("run_*.log"))
            assert len(log_files) == 1
            print("✓ Log file created")

            # Test 4: Verify log file content (JSON format)
            with open(log_files[0], 'r') as f:
                lines = f.readlines()
                assert len(lines) > 0

                # Parse first line as JSON
                log_entry = json.loads(lines[0])
                assert "run_id" in log_entry
                assert log_entry["run_id"] == run_id
                print("✓ Log file contains structured JSON data")

            # Test 5: Test log capture
            with LogCapture("hal") as capture:
                hal_logger = get_logger("hal.test")
                hal_logger.info("Captured message")
                hal_logger.error("Captured error")

                logs = capture.get_logs()
                assert len(logs) >= 2

                error_logs = capture.get_logs("ERROR")
                assert len(error_logs) >= 1
                print("✓ Log capture functionality working")

    except Exception as e:
        print(f"✗ Logging test failed: {e}")
        return False

    return True


def test_integration():
    """Test integration of all core services."""
    print("\nTesting service integration...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup integrated environment
            config = SystemConfig()
            config.paths.log_dir = Path(temp_dir) / "logs"
            config.paths.test_data_dir = Path(temp_dir) / "test_data"

            # Initialize logging
            run_id = setup_logging(config)
            logger = get_logger(__name__)
            logger.info("Starting integrated test")

            # Initialize storage
            storage = FileSystemStorage(config.paths.test_data_dir)
            logger.info("File storage initialized")

            # Create test run with configuration snapshot
            storage.create_test_run(run_id, config)
            logger.info(f"Test run {run_id} created")

            # Simulate test execution
            result_id = storage.create_test_result(run_id, "integration_test")
            logger.info("Test result created")

            # Add some measurements
            storage.add_measurement(result_id, "test_metric", 42.0, "units", {"min": 40, "max": 45})
            logger.info("Measurement recorded")

            # Complete the test
            storage.update_test_result(result_id, "PASSED", 0.5)
            storage.update_test_run(run_id, "COMPLETED", total_tests=1, passed_tests=1)
            logger.info("Test completed successfully")

            # Verify data consistency
            summary = storage.get_run_summary(run_id)
            assert summary["run_id"] == run_id
            assert summary["status"] == "COMPLETED"

            # Verify configuration was stored correctly
            stored_config = summary["configuration_snapshot"]
            if isinstance(stored_config, str):
                stored_config = json.loads(stored_config)
            assert stored_config["test_timeout"] == config.test_timeout

            logger.info("Integration test completed successfully")
            print("✓ All services integrated successfully")

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        return False

    return True


def main():
    """Run all integration tests."""
    print("Phase 1 Core Infrastructure Integration Test")
    print("=" * 50)

    tests = [
        test_configuration_management,
        test_file_storage_operations,
        test_logging_system,
        test_integration
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            break  # Stop on first failure

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All Phase 1 core services are working correctly!")
        print("\nNext steps:")
        print("- Proceed to Phase 2: Implement Hardware Abstraction Layer")
        print("- Create instrument interfaces and VISA backend")
        print("- Develop concrete instrument drivers")
        return True
    else:
        print("❌ Some tests failed. Please fix issues before proceeding.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)