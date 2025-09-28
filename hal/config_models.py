"""Configuration models for the hardware test ecosystem."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class InstrumentConfig(BaseModel):
    """Configuration for a single instrument."""

    address: str = Field(..., description="VISA address of the instrument")
    timeout: int = Field(default=5000, description="Communication timeout in milliseconds")

    @field_validator("timeout")
    @classmethod
    def timeout_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Timeout must be positive")
        return v


class PathsConfig(BaseModel):
    """Configuration for file system paths."""

    log_dir: Path = Field(default=Path("logs"), description="Directory for log files")
    report_dir: Path = Field(default=Path("reports"), description="Directory for reports")
    test_data_dir: Path = Field(default=Path("test_data"), description="Directory for test results and measurements")

    @field_validator("log_dir", "report_dir", "test_data_dir", mode="before")
    @classmethod
    def ensure_path_exists(cls, v: str | Path) -> Path:
        """Ensure directories exist."""
        if isinstance(v, str):
            v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v


class LoggingConfig(BaseModel):
    """Configuration for the logging framework."""

    level: str = Field(default="INFO", description="Log level")
    format_console: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(run_id)s - %(message)s",
        description="Console log format"
    )
    format_file: str = Field(
        default='{"timestamp": "%(asctime)s", "logger": "%(name)s", "level": "%(levelname)s", "run_id": "%(run_id)s", "message": "%(message)s"}',
        description="File log format (JSON)"
    )

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Level must be one of {valid_levels}")
        return v.upper()


class SystemConfig(BaseModel):
    """Main system configuration."""

    # Instrument configurations
    power_supply: Optional[InstrumentConfig] = None
    multimeter: Optional[InstrumentConfig] = None
    oscilloscope: Optional[InstrumentConfig] = None
    function_generator: Optional[InstrumentConfig] = None

    # System paths
    paths: PathsConfig = Field(default_factory=PathsConfig)

    # Logging configuration
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Test execution settings
    test_timeout: int = Field(default=300, description="Default test timeout in seconds")
    parallel_tests: bool = Field(default=False, description="Enable parallel test execution")

    @field_validator("test_timeout")
    @classmethod
    def test_timeout_must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Test timeout must be positive")
        return v
