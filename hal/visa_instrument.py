"""VISA communication backend for instrument control."""

import time
from typing import List, Optional, Union, Any

import pyvisa
import pyvisa.errors

from .interfaces import CommunicationError
from .logging_config import get_logger, log_instrument_command
from .retry_utils import retry_on_communication_error, RetryConfig


class VisaInstrument:
    """
    Base class providing VISA communication capabilities.

    This class handles the low-level VISA communication, error handling,
    and logging for all VISA-based instruments.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 5000, retry_config: Optional[RetryConfig] = None):
        """
        Initialize VISA instrument.

        Args:
            address: VISA address string (can be set later with connect())
            timeout: Communication timeout in milliseconds
            retry_config: Configuration for retry behavior (uses default if None)
        """
        self.address = address
        self.timeout = timeout
        self.retry_config = retry_config or RetryConfig()
        self._resource_manager: Optional[pyvisa.ResourceManager] = None
        self._instrument: Optional[Any] = None  # pyvisa.Resource has complex typing
        self._logger = get_logger(f"{__name__}.{self.__class__.__name__}")
        self._connected = False
        self._model_info: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Return True if instrument is connected and responsive."""
        if not self._connected or not self._instrument:
            return False

        try:
            # Test connection with a simple query
            self._query("*IDN?", timeout=1000)
            return True
        except (CommunicationError, pyvisa.errors.VisaIOError):
            self._connected = False
            return False

    def connect(self, address: Optional[str] = None) -> None:
        """
        Establish connection to the instrument.

        Args:
            address: VISA address string (overrides constructor value)

        Raises:
            CommunicationError: If connection fails
        """
        if address:
            self.address = address

        if not self.address:
            raise CommunicationError("No VISA address specified")

        try:
            # Create resource manager if needed
            if self._resource_manager is None:
                self._resource_manager = pyvisa.ResourceManager()
                self._logger.debug(f"Created VISA ResourceManager: {self._resource_manager}")

            # Open instrument resource
            self._instrument = self._resource_manager.open_resource(self.address)
            self._instrument.timeout = self.timeout

            # Configure common settings
            if hasattr(self._instrument, 'read_termination'):
                self._instrument.read_termination = '\n'
            if hasattr(self._instrument, 'write_termination'):
                self._instrument.write_termination = '\n'

            self._connected = True
            self._logger.info(f"Connected to instrument at {self.address}")

            # Get instrument identification
            try:
                self._model_info = self._query("*IDN?")
                self._logger.info(f"Instrument ID: {self._model_info}")
            except Exception as e:
                self._logger.warning(f"Could not read instrument ID: {e}")

        except pyvisa.errors.VisaIOError as e:
            self._connected = False
            raise CommunicationError(f"Failed to connect to {self.address}: {e}")
        except Exception as e:
            self._connected = False
            raise CommunicationError(f"Unexpected error connecting to {self.address}: {e}")

    def disconnect(self) -> None:
        """Close the connection to the instrument."""
        if self._instrument:
            try:
                self._instrument.close()
                self._logger.info(f"Disconnected from {self.address}")
            except Exception as e:
                self._logger.warning(f"Error during disconnect: {e}")
            finally:
                self._instrument = None

        if self._resource_manager:
            try:
                self._resource_manager.close()
            except Exception as e:
                self._logger.warning(f"Error closing resource manager: {e}")
            finally:
                self._resource_manager = None

        self._connected = False

    def _write(self, command: str) -> None:
        """
        Send a command to the instrument.

        Args:
            command: SCPI command string

        Raises:
            CommunicationError: If write operation fails
        """
        @retry_on_communication_error(self.retry_config)
        def _do_write():
            if not self._instrument or not self._connected:
                raise CommunicationError("Instrument not connected")

            try:
                self._instrument.write(command)
                log_instrument_command(self._logger, self.address or "unknown", command)
            except pyvisa.errors.VisaIOError as e:
                self._connected = False
                raise CommunicationError(f"Write failed: {e}")

        _do_write()

    def _read(self, timeout: Optional[int] = None) -> str:
        """
        Read a response from the instrument.

        Args:
            timeout: Optional timeout in milliseconds

        Returns:
            Response string from instrument

        Raises:
            CommunicationError: If read operation fails
        """
        if not self._instrument or not self._connected:
            raise CommunicationError("Instrument not connected")

        original_timeout = None
        try:
            # Set temporary timeout if specified
            if timeout is not None:
                original_timeout = self._instrument.timeout
                self._instrument.timeout = timeout

            response = self._instrument.read().strip()
            return response

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                raise CommunicationError(f"Read timeout: {e}")
            else:
                self._connected = False
                raise CommunicationError(f"Read failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None and self._instrument:
                self._instrument.timeout = original_timeout

    def _query(self, command: str, timeout: Optional[int] = None) -> str:
        """
        Send a query command and read the response.

        Args:
            command: SCPI query command string
            timeout: Optional timeout in milliseconds

        Returns:
            Response string from instrument

        Raises:
            CommunicationError: If query operation fails
        """
        if not self._instrument or not self._connected:
            raise CommunicationError("Instrument not connected")

        original_timeout = None
        try:
            # Set temporary timeout if specified
            if timeout is not None:
                original_timeout = self._instrument.timeout
                self._instrument.timeout = timeout

            response = self._instrument.query(command).strip()
            log_instrument_command(self._logger, self.address or "unknown", command, response)
            return response

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                raise CommunicationError(f"Query timeout: {e}")
            else:
                self._connected = False
                raise CommunicationError(f"Query failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None and self._instrument:
                self._instrument.timeout = original_timeout

    def _query_binary(self, command: str, timeout: Optional[int] = None) -> bytes:
        """
        Send a query command and read binary response.

        Args:
            command: SCPI query command string
            timeout: Optional timeout in milliseconds

        Returns:
            Binary response from instrument

        Raises:
            CommunicationError: If query operation fails
        """
        if not self._instrument or not self._connected:
            raise CommunicationError("Instrument not connected")

        original_timeout = None
        try:
            # Set temporary timeout if specified
            if timeout is not None:
                original_timeout = self._instrument.timeout
                self._instrument.timeout = timeout

            response = self._instrument.query_binary_values(command, datatype='B', container=bytes)
            log_instrument_command(self._logger, self.address or "unknown", command, f"<{len(response)} bytes>")
            return response

        except pyvisa.errors.VisaIOError as e:
            if "timeout" in str(e).lower():
                raise CommunicationError(f"Binary query timeout: {e}")
            else:
                self._connected = False
                raise CommunicationError(f"Binary query failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None and self._instrument:
                self._instrument.timeout = original_timeout

    def _identify(self) -> str:
        """
        Query instrument identification.

        Returns:
            Instrument identification string

        Raises:
            CommunicationError: If identification query fails
        """
        return self._query("*IDN?")

    def reset(self) -> None:
        """Send a reset command (*RST) to the instrument."""
        self._write("*RST")
        # Wait for reset to complete
        time.sleep(1.0)

    def self_test(self) -> bool:
        """
        Perform instrument self-test.

        Returns:
            True if self-test passes, False otherwise
        """
        try:
            response = self._query("*TST?")
            # Most instruments return "0" for pass, non-zero for fail
            return response.strip() == "0"
        except CommunicationError:
            return False

    def get_error_queue(self) -> List[str]:
        """
        Read and clear the instrument's error queue.

        Returns:
            List of error messages from the instrument
        """
        errors = []
        try:
            while True:
                error = self._query("SYST:ERR?")
                if error.startswith("0,") or error.startswith("+0,"):
                    # No more errors
                    break
                errors.append(error)

                # Safety check to prevent infinite loop
                if len(errors) > 100:
                    self._logger.warning("Error queue exceeded 100 entries, stopping read")
                    break
        except CommunicationError as e:
            self._logger.warning(f"Could not read error queue: {e}")

        return errors

    def wait_for_completion(self, timeout: float = 10.0) -> bool:
        """
        Wait for all pending operations to complete.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if operations completed, False if timeout
        """
        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                status = self._query("*OPC?")
                if status.strip() == "1":
                    return True
                time.sleep(0.1)
        except CommunicationError:
            pass

        self._logger.warning(f"Operation completion timeout after {timeout}s")
        return False

    def __enter__(self) -> "VisaInstrument":
        """Context manager entry."""
        if not self.is_connected and self.address:
            self.connect()
        return self

    def __exit__(self, exc_type: type, exc_val: Exception, exc_tb: object) -> None:
        """Context manager exit."""
        self.disconnect()

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        try:
            self.disconnect()
        except Exception:
            pass  # Ignore errors during cleanup


class MockVisaInstrument(VisaInstrument):
    """
    Mock VISA instrument for testing without hardware.

    This class simulates instrument responses for development and testing.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 5000):
        """Initialize mock instrument."""
        super().__init__(address, timeout)
        self._mock_responses = {
            "*IDN?": "Mock Instrument,Model 1234,Serial 5678,Version 1.0.0",
            "*TST?": "0",
            "*OPC?": "1",
            "SYST:ERR?": "0,No Error"
        }
        self._mock_connected = False

    def connect(self, address: Optional[str] = None) -> None:
        """Mock connection that always succeeds."""
        if address:
            self.address = address
        if not self.address:
            self.address = "MOCK::INSTRUMENT"

        self._mock_connected = True
        self._connected = True
        self._logger.info(f"Mock connected to {self.address}")

    def disconnect(self) -> None:
        """Mock disconnection."""
        self._mock_connected = False
        self._connected = False
        self._logger.info("Mock disconnected")

    @property
    def is_connected(self) -> bool:
        """Return mock connection status."""
        return self._mock_connected

    def _write(self, command: str) -> None:
        """Mock write operation."""
        if not self._mock_connected:
            raise CommunicationError("Mock instrument not connected")
        log_instrument_command(self._logger, self.address or "mock", command)

    def _read(self, timeout: Optional[int] = None) -> str:
        """Mock read operation."""
        if not self._mock_connected:
            raise CommunicationError("Mock instrument not connected")
        return "MOCK_RESPONSE"

    def _query(self, command: str, timeout: Optional[int] = None) -> str:
        """Mock query operation with predefined responses."""
        if not self._mock_connected:
            raise CommunicationError("Mock instrument not connected")

        response = self._mock_responses.get(command, "MOCK_RESPONSE")
        log_instrument_command(self._logger, self.address or "mock", command, response)
        return response

    def add_mock_response(self, command: str, response: str) -> None:
        """Add a custom mock response for a command."""
        self._mock_responses[command] = response
