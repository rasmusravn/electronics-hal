"""Driver for Keysight E36100 Series Programmable DC Power Supplies."""

from typing import Optional, Any

from ..interfaces import PowerSupply
from ..visa_instrument import VisaInstrument


class KeysightE36100Series(VisaInstrument, PowerSupply):
    """
    Driver for Keysight E36100 Series Power Supplies.

    Supports models: E36102A, E36103A, E36104A, E36105A, E36106A
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 5000):
        """
        Initialize the power supply driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds
        """
        super().__init__(address, timeout)
        self._model_name = ""
        self._serial_number = ""
        self._num_channels = 1  # Will be determined from model

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the power supply and identify model."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

            # Determine number of channels based on model
            if "E36102" in self._model_name or "E36103" in self._model_name:
                self._num_channels = 2
            elif "E36104" in self._model_name or "E36105" in self._model_name:
                self._num_channels = 3
            elif "E36106" in self._model_name:
                self._num_channels = 4
            else:
                self._num_channels = 1

        # Initialize the instrument
        self.reset()
        # Clear error queue
        self.get_error_queue()

    @property
    def model_name(self) -> str:
        """Return the instrument's model name."""
        return self._model_name

    @property
    def serial_number(self) -> str:
        """Return the instrument's serial number."""
        return self._serial_number

    @property
    def num_channels(self) -> int:
        """Return the number of output channels."""
        return self._num_channels

    def _validate_channel(self, channel: int) -> None:
        """Validate channel number is within range."""
        if not 1 <= channel <= self._num_channels:
            raise ValueError(f"Channel {channel} invalid. Valid range: 1-{self._num_channels}")

    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """Set the output voltage for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:VOLT {voltage}")
        else:
            self._write(f"VOLT {voltage}")

    def get_voltage(self, channel: int = 1) -> float:
        """Get the current voltage setting for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:VOLT?")
        else:
            response = self._query("VOLT?")
        return float(response)

    def measure_voltage(self, channel: int = 1) -> float:
        """Measure the actual output voltage for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"MEAS:VOLT? CH{channel}")
        else:
            response = self._query("MEAS:VOLT?")
        return float(response)

    def set_current_limit(self, current: float, channel: int = 1) -> None:
        """Set the current limit for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:CURR {current}")
        else:
            self._write(f"CURR {current}")

    def get_current_limit(self, channel: int = 1) -> float:
        """Get the current limit setting for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:CURR?")
        else:
            response = self._query("CURR?")
        return float(response)

    def measure_current(self, channel: int = 1) -> float:
        """Measure the actual output current for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"MEAS:CURR? CH{channel}")
        else:
            response = self._query("MEAS:CURR?")
        return float(response)

    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """Enable or disable the output for a channel."""
        self._validate_channel(channel)
        state = "ON" if enabled else "OFF"
        if self._num_channels > 1:
            self._write(f"OUTP{channel} {state}")
        else:
            self._write(f"OUTP {state}")

    def get_output_state(self, channel: int = 1) -> bool:
        """Get the output state for a channel."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"OUTP{channel}?")
        else:
            response = self._query("OUTP?")
        return response.strip() == "1"

    def set_ovp_threshold(self, threshold: float, channel: int = 1) -> None:
        """Set the over-voltage protection threshold."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:VOLT:PROT {threshold}")
        else:
            self._write(f"VOLT:PROT {threshold}")

    def get_ovp_threshold(self, channel: int = 1) -> float:
        """Get the over-voltage protection threshold."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:VOLT:PROT?")
        else:
            response = self._query("VOLT:PROT?")
        return float(response)

    def set_ocp_threshold(self, threshold: float, channel: int = 1) -> None:
        """
        Set the over-current protection threshold.

        Args:
            threshold: OCP threshold in amperes
            channel: Output channel number
        """
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:CURR:PROT {threshold}")
        else:
            self._write(f"CURR:PROT {threshold}")

    def get_ocp_threshold(self, channel: int = 1) -> float:
        """
        Get the over-current protection threshold.

        Args:
            channel: Output channel number

        Returns:
            OCP threshold in amperes
        """
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:CURR:PROT?")
        else:
            response = self._query("CURR:PROT?")
        return float(response)

    def get_status(self, channel: int = 1) -> dict:
        """
        Get comprehensive status information for a channel.

        Args:
            channel: Output channel number

        Returns:
            Dictionary containing voltage, current, output state, and limits
        """
        self._validate_channel(channel)

        status = {
            "voltage_set": self.get_voltage(channel),
            "voltage_measured": self.measure_voltage(channel),
            "current_limit": self.get_current_limit(channel),
            "current_measured": self.measure_current(channel),
            "output_enabled": self.get_output_state(channel),
            "ovp_threshold": self.get_ovp_threshold(channel),
            "ocp_threshold": self.get_ocp_threshold(channel),
        }

        return status

    def configure_channel(
        self,
        channel: int,
        voltage: float,
        current_limit: float,
        output_enabled: bool = False
    ) -> None:
        """
        Configure a channel with all basic parameters.

        Args:
            channel: Output channel number
            voltage: Output voltage in volts
            current_limit: Current limit in amperes
            output_enabled: Whether to enable output immediately
        """
        self._validate_channel(channel)

        # Set parameters in safe order (output off, set limits, set voltage, enable if requested)
        self.set_output_state(False, channel)
        self.set_current_limit(current_limit, channel)
        self.set_voltage(voltage, channel)

        if output_enabled:
            self.set_output_state(True, channel)

        self._logger.info(f"Channel {channel} configured: {voltage}V, {current_limit}A limit, output {'ON' if output_enabled else 'OFF'}")


class MockKeysightE36100Series(KeysightE36100Series):
    """Mock version of Keysight E36100 Series for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 5000, model: str = "E36103A"):
        """
        Initialize mock power supply.

        Args:
            address: Mock VISA address
            timeout: Communication timeout
            model: Model to simulate (E36102A, E36103A, etc.)
        """
        super().__init__(address, timeout)
        self._mock_model = model
        self._mock_states: dict[str, Any] = {}
        self._init_mock_states()

    def _init_mock_states(self) -> None:
        """Initialize mock internal states."""
        # Determine number of channels
        if "E36102" in self._mock_model or "E36103" in self._mock_model:
            self._num_channels = 2
        elif "E36104" in self._mock_model or "E36105" in self._mock_model:
            self._num_channels = 3
        elif "E36106" in self._mock_model:
            self._num_channels = 4
        else:
            self._num_channels = 1

        # Initialize states for each channel
        for ch in range(1, self._num_channels + 1):
            self._mock_states[ch] = {
                "voltage": 0.0,
                "current_limit": 1.0,
                "output_enabled": False,
                "ovp_threshold": 10.0,
                "ocp_threshold": 2.0,
                "measured_voltage": 0.0,
                "measured_current": 0.0,
            }

    @property
    def is_connected(self) -> bool:
        """Return mock connection status."""
        return getattr(self, '_connected', False)

    def connect(self, address: Optional[str] = None) -> None:
        """Mock connection."""
        if address:
            self.address = address
        if not self.address:
            self.address = f"MOCK::{self._mock_model}"

        self._connected = True
        self._model_name = self._mock_model
        self._serial_number = "MOCK123456"
        self._logger.info(f"Mock {self._mock_model} connected at {self.address}")

    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """Mock set voltage."""
        self._validate_channel(channel)
        self._mock_states[channel]["voltage"] = voltage
        # Simulate measured voltage equals set voltage when output is on
        if self._mock_states[channel]["output_enabled"]:
            self._mock_states[channel]["measured_voltage"] = voltage
        self._logger.debug(f"Mock CH{channel} voltage set to {voltage}V")

    def get_voltage(self, channel: int = 1) -> float:
        """Mock get voltage."""
        self._validate_channel(channel)
        return self._mock_states[channel]["voltage"]

    def measure_voltage(self, channel: int = 1) -> float:
        """Mock measure voltage."""
        self._validate_channel(channel)
        return self._mock_states[channel]["measured_voltage"]

    def set_current_limit(self, current: float, channel: int = 1) -> None:
        """Mock set current limit."""
        self._validate_channel(channel)
        self._mock_states[channel]["current_limit"] = current
        self._logger.debug(f"Mock CH{channel} current limit set to {current}A")

    def get_current_limit(self, channel: int = 1) -> float:
        """Mock get current limit."""
        self._validate_channel(channel)
        return self._mock_states[channel]["current_limit"]

    def measure_current(self, channel: int = 1) -> float:
        """Mock measure current."""
        self._validate_channel(channel)
        return self._mock_states[channel]["measured_current"]

    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """Mock set output state."""
        self._validate_channel(channel)
        self._mock_states[channel]["output_enabled"] = enabled
        # Update measured voltage based on output state
        if enabled:
            self._mock_states[channel]["measured_voltage"] = self._mock_states[channel]["voltage"]
            # Simulate small load current
            self._mock_states[channel]["measured_current"] = 0.001
        else:
            self._mock_states[channel]["measured_voltage"] = 0.0
            self._mock_states[channel]["measured_current"] = 0.0
        self._logger.debug(f"Mock CH{channel} output {'enabled' if enabled else 'disabled'}")

    def get_output_state(self, channel: int = 1) -> bool:
        """Mock get output state."""
        self._validate_channel(channel)
        return self._mock_states[channel]["output_enabled"]

    def set_ovp_threshold(self, threshold: float, channel: int = 1) -> None:
        """Mock set OVP threshold."""
        self._validate_channel(channel)
        self._mock_states[channel]["ovp_threshold"] = threshold

    def get_ovp_threshold(self, channel: int = 1) -> float:
        """Mock get OVP threshold."""
        self._validate_channel(channel)
        return self._mock_states[channel]["ovp_threshold"]

    def set_ocp_threshold(self, threshold: float, channel: int = 1) -> None:
        """Mock set OCP threshold."""
        self._validate_channel(channel)
        self._mock_states[channel]["ocp_threshold"] = threshold

    def get_ocp_threshold(self, channel: int = 1) -> float:
        """Mock get OCP threshold."""
        self._validate_channel(channel)
        return self._mock_states[channel]["ocp_threshold"]

    def reset(self) -> None:
        """Mock reset - just reset internal states."""
        for ch in range(1, self._num_channels + 1):
            self._mock_states[ch].update({
                "voltage": 0.0,
                "output_enabled": False,
                "measured_voltage": 0.0,
                "measured_current": 0.0,
            })
        self._logger.debug("Mock power supply reset")

    def self_test(self) -> bool:
        """Mock self test - always passes."""
        return True

    def get_error_queue(self) -> list:
        """Mock error queue - no errors."""
        return []
