"""Centralized logging configuration for the test ecosystem."""

import logging
import logging.config
import uuid
from typing import Optional

from .config_models import SystemConfig


class ContextFilter(logging.Filter):
    """Custom filter to inject test run context into log records."""

    def __init__(self, run_id: str):
        """
        Initialize the context filter.

        Args:
            run_id: Unique identifier for the test run
        """
        super().__init__()
        self.run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Add run_id to the log record.

        Args:
            record: Log record to filter

        Returns:
            True to allow the record to be processed
        """
        record.run_id = self.run_id
        return True


class JSONFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        import json

        log_data = {
            "timestamp": self.formatTime(record),
            "logger": record.name,
            "level": record.levelname,
            "run_id": getattr(record, "run_id", "unknown"),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields
        for key, value in record.__dict__.items():
            if key not in log_data and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data, default=str)


def setup_logging(config: SystemConfig, run_id: Optional[str] = None) -> str:
    """
    Configure the logging system.

    Args:
        config: System configuration
        run_id: Test run identifier. If None, a new UUID will be generated.

    Returns:
        The run_id used for logging
    """
    if run_id is None:
        run_id = str(uuid.uuid4())

    # Ensure log directory exists
    log_dir = config.paths.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create unique log file name
    log_file = log_dir / f"run_{run_id}.log"

    # Build logging configuration
    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "console": {
                "format": config.logging.format_console,
                "datefmt": "%Y-%m-%d %H:%M:%S"
            },
            "json": {
                "()": JSONFormatter,
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "filters": {
            "context": {
                "()": ContextFilter,
                "run_id": run_id
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": config.logging.level,
                "formatter": "console",
                "filters": ["context"],
                "stream": "ext://sys.stdout"
            },
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",  # Always capture debug and above to file
                "formatter": "json",
                "filters": ["context"],
                "filename": str(log_file),
                "mode": "w"  # Overwrite file for each run
            }
        },
        "root": {
            "level": "DEBUG",
            "handlers": ["console", "file"]
        },
        "loggers": {
            "hal": {
                "level": "DEBUG",
                "propagate": True
            },
            "tests": {
                "level": "DEBUG",
                "propagate": True
            }
        }
    }

    # Apply the configuration
    logging.config.dictConfig(logging_config)

    # Log the initialization
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized for test run {run_id}")
    logger.debug(f"Log file: {log_file}")

    return run_id


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class LogCapture:
    """Context manager for capturing logs during test execution."""

    def __init__(self, logger_name: str = ""):
        """
        Initialize log capture.

        Args:
            logger_name: Name of logger to capture (empty for root)
        """
        self.logger_name = logger_name
        self.handler: Optional[logging.Handler] = None
        self.logs: list = []

    def __enter__(self) -> "LogCapture":
        """Start capturing logs."""
        # Create a memory handler to capture logs
        class CaptureHandler(logging.Handler):
            def __init__(self, capture_func):
                super().__init__()
                self.capture_func = capture_func

            def emit(self, record):
                self.capture_func(record)

        self.handler = CaptureHandler(self._capture_log)

        # Add handler to the specified logger
        logger = logging.getLogger(self.logger_name)
        logger.addHandler(self.handler)

        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Stop capturing logs."""
        if self.handler:
            logger = logging.getLogger(self.logger_name)
            logger.removeHandler(self.handler)

    def _capture_log(self, record: logging.LogRecord) -> None:
        """Capture a log record."""
        self.logs.append({
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": record.created,
            "logger": record.name
        })

    def get_logs(self, level: Optional[str] = None) -> list:
        """
        Get captured logs.

        Args:
            level: Optional level filter

        Returns:
            List of log records
        """
        if level is None:
            return self.logs.copy()
        return [log for log in self.logs if log["level"] == level]


def log_instrument_command(logger: logging.Logger, instrument: str, command: str, response: Optional[str] = None) -> None:
    """
    Log an instrument command with structured data.

    Args:
        logger: Logger instance
        instrument: Instrument identifier
        command: Command sent to instrument
        response: Optional response from instrument
    """
    extra_data = {
        "instrument": instrument,
        "command": command,
        "command_type": "query" if "?" in command else "write"
    }

    if response is not None:
        extra_data["response"] = response
        logger.debug(f"INSTRUMENT QUERY: {instrument} <- {command} -> {response}", extra=extra_data)
    else:
        logger.debug(f"INSTRUMENT WRITE: {instrument} <- {command}", extra=extra_data)
