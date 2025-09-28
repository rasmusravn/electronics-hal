"""
Unit tests for configuration validation and loading.

These tests verify the configuration system works correctly
without requiring hardware or complex setup.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from hal.config_loader import ConfigurationError, create_example_config, load_config
from hal.config_models import InstrumentConfig, PathsConfig, SystemConfig


class TestConfigurationValidation:
    """Test configuration loading and validation."""

    @pytest.mark.unit
    def test_default_configuration_loading(self):
        """Test loading default configuration when no file exists."""
        config = load_config(Path("nonexistent_file.yml"))

        assert isinstance(config, SystemConfig)
        assert config.test_timeout == 300
        assert not config.parallel_tests
        assert config.logging.level == "INFO"

    @pytest.mark.unit
    def test_valid_configuration_loading(self):
        """Test loading a valid configuration file."""
        config_data = {
            "power_supply": {
                "address": "USB0::0x0957::0x8C07::MY52200021::INSTR",
                "timeout": 5000
            },
            "multimeter": {
                "address": "USB0::0x2A8D::0x0201::MY59003456::INSTR",
                "timeout": 3000
            },
            "logging": {
                "level": "DEBUG"
            },
            "test_timeout": 600
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            config = load_config(Path(f.name))

        assert config.power_supply.address == "USB0::0x0957::0x8C07::MY52200021::INSTR"
        assert config.power_supply.timeout == 5000
        assert config.multimeter.timeout == 3000
        assert config.logging.level == "DEBUG"
        assert config.test_timeout == 600

    @pytest.mark.unit
    def test_invalid_timeout_validation(self):
        """Test that invalid timeout values are rejected."""
        with pytest.raises(ValueError, match="Test timeout must be positive"):
            SystemConfig(test_timeout=-10)

    @pytest.mark.unit
    def test_invalid_log_level_validation(self):
        """Test that invalid log levels are rejected."""
        config_data = {
            "logging": {
                "level": "INVALID_LEVEL"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            with pytest.raises(ConfigurationError, match="validation failed"):
                load_config(Path(f.name))

    @pytest.mark.unit
    def test_instrument_timeout_validation(self):
        """Test instrument timeout validation."""
        # Valid timeout
        inst = InstrumentConfig(address="TEST", timeout=5000)
        assert inst.timeout == 5000

        # Invalid timeout (should raise ValidationError)
        with pytest.raises(ValueError, match="Timeout must be positive"):
            InstrumentConfig(address="TEST", timeout=-1000)

    @pytest.mark.unit
    def test_paths_configuration(self):
        """Test paths configuration and directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            paths = PathsConfig(
                log_dir=temp_path / "logs",
                report_dir=temp_path / "reports",
                test_data_dir=temp_path / "test_data"
            )

            # Directories should be created automatically
            assert paths.log_dir.exists()
            assert paths.report_dir.exists()
            assert paths.test_data_dir.exists()

    @pytest.mark.unit
    def test_example_config_creation(self):
        """Test creation of example configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            example_path = Path(temp_dir) / "example.yml"

            create_example_config(example_path)

            assert example_path.exists()

            # Load and verify the example config
            config = load_config(example_path)
            assert config.power_supply is not None
            assert config.multimeter is not None
            assert "USB0" in config.power_supply.address

    @pytest.mark.unit
    def test_nested_configuration_override(self):
        """Test that nested configuration values can be overridden."""
        base_config = SystemConfig()

        # Test default values
        assert base_config.logging.level == "INFO"
        assert base_config.paths.log_dir == Path("logs")

        # Test override with a temporary directory path
        with tempfile.TemporaryDirectory() as temp_dir:
            custom_log_path = Path(temp_dir) / "custom_logs"

            config_data = {
                "logging": {"level": "WARNING"},
                "paths": {"log_dir": str(custom_log_path)}
            }

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
                yaml.dump(config_data, f)
                f.flush()

                config = load_config(Path(f.name))

            assert config.logging.level == "WARNING"
            assert config.paths.log_dir == custom_log_path

    @pytest.mark.unit
    def test_malformed_yaml_handling(self):
        """Test handling of malformed YAML files."""
        malformed_yaml = """
        power_supply:
          address: "USB0::test"
          timeout: 5000
        invalid_yaml: [unclosed bracket
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(malformed_yaml)
            f.flush()

            with pytest.raises(ConfigurationError, match="Failed to parse YAML"):
                load_config(Path(f.name))
