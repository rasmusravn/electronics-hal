"""Configuration loading and management."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import ValidationError

from .config_models import SystemConfig


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""


def load_config(config_path: Optional[Path] = None) -> SystemConfig:
    """
    Load and validate system configuration.

    Args:
        config_path: Path to the configuration file. Defaults to config/config.yml

    Returns:
        Validated SystemConfig instance

    Raises:
        ConfigurationError: If configuration loading or validation fails
    """
    if config_path is None:
        config_path = Path("config/config.yml")

    # Load configuration from YAML file if it exists
    config_data: dict = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML config: {e}") from e
        except OSError as e:
            raise ConfigurationError(f"Failed to read config file: {e}") from e

    # Override with environment variables if present
    # This allows for deployment-specific configuration
    env_overrides = _load_env_overrides()
    if env_overrides:
        config_data.update(env_overrides)

    # Validate and create configuration object
    try:
        return SystemConfig(**config_data)
    except ValidationError as e:
        raise ConfigurationError(f"Configuration validation failed: {e}") from e


def _load_env_overrides() -> dict:
    """Load configuration overrides from environment variables."""
    overrides: dict = {}

    # Example environment variable mappings
    env_mappings = {
        "HAL_LOG_LEVEL": ("logging", "level"),
        "HAL_DB_PATH": ("paths", "db_path"),
        "HAL_LOG_DIR": ("paths", "log_dir"),
        "HAL_REPORT_DIR": ("paths", "report_dir"),
        "HAL_POWER_SUPPLY_ADDRESS": ("power_supply", "address"),
        "HAL_MULTIMETER_ADDRESS": ("multimeter", "address"),
        "HAL_TEST_TIMEOUT": ("test_timeout",),
    }

    for env_var, config_path in env_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            # Navigate nested dictionary structure
            current = overrides
            for key in config_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[config_path[-1]] = value

    return overrides


def create_example_config(output_path: Path = Path("config/config.yml.example")) -> None:
    """Create an example configuration file."""
    example_config = {
        "power_supply": {
            "address": "USB0::0x0957::0x8C07::MY52200021::INSTR",
            "timeout": 5000
        },
        "multimeter": {
            "address": "USB0::0x2A8D::0x0201::MY59003456::INSTR",
            "timeout": 3000
        },
        "paths": {
            "log_dir": "logs",
            "report_dir": "reports",
            "db_path": "test_results.db"
        },
        "logging": {
            "level": "INFO"
        },
        "test_timeout": 300,
        "parallel_tests": False
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        yaml.dump(example_config, f, default_flow_style=False, sort_keys=False)
