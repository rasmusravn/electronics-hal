"""Retry utilities for robust instrument communication."""

import time
from typing import Any, Callable, Optional, Type, Union
from functools import wraps

from .interfaces import CommunicationError
from .logging_config import get_logger


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 2.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            backoff_factor: Multiplier for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


def retry_on_communication_error(
    config: Optional[RetryConfig] = None,
    exceptions: tuple[Type[Exception], ...] = (CommunicationError,)
) -> Callable:
    """
    Decorator for retrying operations that may fail due to communication errors.

    Args:
        config: Retry configuration (uses default if None)
        exceptions: Tuple of exception types to retry on

    Returns:
        Decorated function with retry behavior
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            logger = get_logger(f"{func.__module__}.{func.__name__}")

            last_exception = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts - 1:
                        # Last attempt failed, re-raise
                        logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.backoff_factor ** attempt),
                        config.max_delay
                    )

                    # Add jitter if enabled
                    if config.jitter:
                        import random
                        delay *= (0.5 + random.random())

                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s"
                    )
                    time.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class ConnectionManager:
    """Manages instrument connections with automatic retry and recovery."""

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """
        Initialize connection manager.

        Args:
            retry_config: Configuration for retry behavior
        """
        self.retry_config = retry_config or RetryConfig()
        self.logger = get_logger(__name__)

    def with_retry(self, instrument, operation: str, *args, **kwargs) -> Any:
        """
        Execute an instrument operation with automatic retry.

        Args:
            instrument: Instrument instance
            operation: Name of the operation method to call
            *args: Arguments to pass to the operation
            **kwargs: Keyword arguments to pass to the operation

        Returns:
            Result of the operation

        Raises:
            CommunicationError: If all retry attempts fail
        """
        @retry_on_communication_error(self.retry_config)
        def _execute():
            # Check if instrument is still connected
            if hasattr(instrument, 'is_connected') and not instrument.is_connected:
                self.logger.info(f"Instrument disconnected, attempting reconnection")
                instrument.connect()

            # Execute the operation
            method = getattr(instrument, operation)
            return method(*args, **kwargs)

        return _execute()

    def ensure_connection(self, instrument) -> None:
        """
        Ensure instrument is connected, with retry on failure.

        Args:
            instrument: Instrument instance to check/connect
        """
        @retry_on_communication_error(self.retry_config)
        def _connect():
            if not instrument.is_connected:
                instrument.connect()

        _connect()

    def safe_disconnect(self, instrument) -> None:
        """
        Safely disconnect from instrument, ignoring errors.

        Args:
            instrument: Instrument instance to disconnect
        """
        try:
            if hasattr(instrument, 'is_connected') and instrument.is_connected:
                instrument.disconnect()
        except Exception as e:
            self.logger.warning(f"Error during safe disconnect: {e}")


# Global connection manager instance
_global_connection_manager = ConnectionManager()


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance."""
    return _global_connection_manager


def set_global_retry_config(config: RetryConfig) -> None:
    """Set the global retry configuration."""
    global _global_connection_manager
    _global_connection_manager = ConnectionManager(config)


# Convenience functions for common retry patterns
def retry_instrument_operation(instrument, operation: str, *args, **kwargs) -> Any:
    """
    Convenience function to retry an instrument operation.

    Args:
        instrument: Instrument instance
        operation: Name of the operation method
        *args: Arguments for the operation
        **kwargs: Keyword arguments for the operation

    Returns:
        Result of the operation
    """
    return get_connection_manager().with_retry(instrument, operation, *args, **kwargs)


def ensure_instrument_connected(instrument) -> None:
    """
    Convenience function to ensure an instrument is connected.

    Args:
        instrument: Instrument instance
    """
    get_connection_manager().ensure_connection(instrument)