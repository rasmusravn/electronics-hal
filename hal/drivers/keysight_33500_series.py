"""Driver for Keysight 33500 Series Function/Waveform Generators."""

from typing import Optional, Any

from ..interfaces import CommunicationError, FunctionGenerator
from ..visa_instrument import VisaInstrument


class Keysight33500Series(VisaInstrument, FunctionGenerator):
    """
    Driver for Keysight 33500 Series Function/Waveform Generators.

    Supports models: 33509B, 33510B, 33511B, 33512B, 33519B, 33520B, 33521B, 33522B
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 5000):
        """
        Initialize the function generator driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds
        """
        super().__init__(address, timeout)
        self._model_name = ""
        self._serial_number = ""
        self._num_channels = 1  # Will be determined from model

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the function generator and identify model."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

            # Determine number of channels based on model
            if any(model in self._model_name for model in ["33512B", "33522B", "33519B", "33520B"]):
                self._num_channels = 2
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

    def _get_channel_suffix(self, channel: int) -> str:
        """Get the channel suffix for commands."""
        if self._num_channels > 1:
            return f"{channel}"
        else:
            return ""

    def set_waveform(self, waveform: str, channel: int = 1) -> None:
        """Set the output waveform type."""
        self._validate_channel(channel)

        # Validate waveform type
        valid_waveforms = ["SIN", "SQU", "TRI", "RAMP", "PULS", "PRBS", "NOIS", "ARB", "DC"]
        if waveform.upper() not in valid_waveforms:
            raise ValueError(f"Invalid waveform: {waveform}. Valid options: {valid_waveforms}")

        if self._num_channels > 1:
            self._write(f"SOUR{channel}:FUNC {waveform}")
        else:
            self._write(f"FUNC {waveform}")

    def get_waveform(self, channel: int = 1) -> str:
        """Get the current waveform type."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:FUNC?")
        else:
            response = self._query("FUNC?")
        return response.strip()

    def set_frequency(self, frequency: float, channel: int = 1) -> None:
        """Set the output frequency."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:FREQ {frequency}")
        else:
            self._write(f"FREQ {frequency}")

    def get_frequency(self, channel: int = 1) -> float:
        """Get the current frequency setting."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:FREQ?")
        else:
            response = self._query("FREQ?")
        return float(response)

    def set_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """Set the output amplitude."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:VOLT {amplitude}")
        else:
            self._write(f"VOLT {amplitude}")

    def get_amplitude(self, channel: int = 1) -> float:
        """Get the current amplitude setting."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:VOLT?")
        else:
            response = self._query("VOLT?")
        return float(response)

    def set_offset(self, offset: float, channel: int = 1) -> None:
        """Set the DC offset."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:VOLT:OFFS {offset}")
        else:
            self._write(f"VOLT:OFFS {offset}")

    def get_offset(self, channel: int = 1) -> float:
        """Get the current DC offset setting."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:VOLT:OFFS?")
        else:
            response = self._query("VOLT:OFFS?")
        return float(response)

    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """Enable or disable the output."""
        self._validate_channel(channel)
        state = "ON" if enabled else "OFF"
        if self._num_channels > 1:
            self._write(f"OUTP{channel} {state}")
        else:
            self._write(f"OUTP {state}")

    def get_output_state(self, channel: int = 1) -> bool:
        """Get the output state."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"OUTP{channel}?")
        else:
            response = self._query("OUTP?")
        return response.strip() == "1"

    def set_phase(self, phase: float, channel: int = 1) -> None:
        """
        Set the phase of the waveform.

        Args:
            phase: Phase in degrees (0 to 360)
            channel: Output channel number
        """
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:PHAS {phase}")
        else:
            self._write(f"PHAS {phase}")

    def get_phase(self, channel: int = 1) -> float:
        """Get the current phase setting."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:PHAS?")
        else:
            response = self._query("PHAS?")
        return float(response)

    def set_duty_cycle(self, duty_cycle: float, channel: int = 1) -> None:
        """
        Set the duty cycle for square waves.

        Args:
            duty_cycle: Duty cycle percentage (10 to 90)
            channel: Output channel number
        """
        self._validate_channel(channel)
        if self._num_channels > 1:
            self._write(f"SOUR{channel}:FUNC:SQU:DCYC {duty_cycle}")
        else:
            self._write(f"FUNC:SQU:DCYC {duty_cycle}")

    def get_duty_cycle(self, channel: int = 1) -> float:
        """Get the current duty cycle setting."""
        self._validate_channel(channel)
        if self._num_channels > 1:
            response = self._query(f"SOUR{channel}:FUNC:SQU:DCYC?")
        else:
            response = self._query("FUNC:SQU:DCYC?")
        return float(response)

    def configure_channel(
        self,
        channel: int,
        waveform: str,
        frequency: float,
        amplitude: float,
        offset: float = 0.0,
        phase: float = 0.0,
        output_enabled: bool = False
    ) -> None:
        """
        Configure a channel with all basic parameters.

        Args:
            channel: Output channel number
            waveform: Waveform type
            frequency: Frequency in Hz
            amplitude: Amplitude in volts peak-to-peak
            offset: DC offset in volts
            phase: Phase in degrees
            output_enabled: Whether to enable output immediately
        """
        self._validate_channel(channel)

        # Set parameters in logical order
        self.set_output_state(False, channel)  # Turn off output first
        self.set_waveform(waveform, channel)
        self.set_frequency(frequency, channel)
        self.set_amplitude(amplitude, channel)
        self.set_offset(offset, channel)
        self.set_phase(phase, channel)

        if output_enabled:
            self.set_output_state(True, channel)

        self._logger.info(
            f"Channel {channel} configured: {waveform}, {frequency}Hz, {amplitude}Vpp, "
            f"{offset}V offset, {phase}° phase, output {'ON' if output_enabled else 'OFF'}"
        )

    def get_status(self, channel: int = 1) -> dict:
        """
        Get comprehensive status information for a channel.

        Args:
            channel: Output channel number

        Returns:
            Dictionary containing all channel settings
        """
        self._validate_channel(channel)

        status = {
            "waveform": self.get_waveform(channel),
            "frequency": self.get_frequency(channel),
            "amplitude": self.get_amplitude(channel),
            "offset": self.get_offset(channel),
            "phase": self.get_phase(channel),
            "output_enabled": self.get_output_state(channel),
        }

        # Add duty cycle if it's a square wave
        try:
            if status["waveform"] == "SQU":
                status["duty_cycle"] = self.get_duty_cycle(channel)
        except CommunicationError:
            pass  # Some models may not support duty cycle query

        return status


class Mock33500Series(Keysight33500Series):
    """Mock version of Keysight 33500 Series for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 5000, model: str = "33511B"):
        """
        Initialize mock function generator.

        Args:
            address: Mock VISA address
            timeout: Communication timeout
            model: Model to simulate
        """
        super().__init__(address, timeout)
        self._mock_model = model
        self._mock_states: dict[str, Any] = {}
        self._init_mock_states()

    def _init_mock_states(self) -> None:
        """Initialize mock internal states."""
        # Determine number of channels
        if any(model in self._mock_model for model in ["33512B", "33522B", "33519B", "33520B"]):
            self._num_channels = 2
        else:
            self._num_channels = 1

        # Initialize states for each channel
        for ch in range(1, self._num_channels + 1):
            self._mock_states[ch] = {
                "waveform": "SIN",
                "frequency": 1000.0,
                "amplitude": 1.0,
                "offset": 0.0,
                "phase": 0.0,
                "duty_cycle": 50.0,
                "output_enabled": False,
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

    def set_waveform(self, waveform: str, channel: int = 1) -> None:
        """Mock set waveform."""
        self._validate_channel(channel)
        self._mock_states[channel]["waveform"] = waveform.upper()
        self._logger.debug(f"Mock CH{channel} waveform set to {waveform}")

    def get_waveform(self, channel: int = 1) -> str:
        """Mock get waveform."""
        self._validate_channel(channel)
        return self._mock_states[channel]["waveform"]

    def set_frequency(self, frequency: float, channel: int = 1) -> None:
        """Mock set frequency."""
        self._validate_channel(channel)
        self._mock_states[channel]["frequency"] = frequency
        self._logger.debug(f"Mock CH{channel} frequency set to {frequency}Hz")

    def get_frequency(self, channel: int = 1) -> float:
        """Mock get frequency."""
        self._validate_channel(channel)
        return self._mock_states[channel]["frequency"]

    def set_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """Mock set amplitude."""
        self._validate_channel(channel)
        self._mock_states[channel]["amplitude"] = amplitude
        self._logger.debug(f"Mock CH{channel} amplitude set to {amplitude}Vpp")

    def get_amplitude(self, channel: int = 1) -> float:
        """Mock get amplitude."""
        self._validate_channel(channel)
        return self._mock_states[channel]["amplitude"]

    def set_offset(self, offset: float, channel: int = 1) -> None:
        """Mock set offset."""
        self._validate_channel(channel)
        self._mock_states[channel]["offset"] = offset
        self._logger.debug(f"Mock CH{channel} offset set to {offset}V")

    def get_offset(self, channel: int = 1) -> float:
        """Mock get offset."""
        self._validate_channel(channel)
        return self._mock_states[channel]["offset"]

    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """Mock set output state."""
        self._validate_channel(channel)
        self._mock_states[channel]["output_enabled"] = enabled
        self._logger.debug(f"Mock CH{channel} output {'enabled' if enabled else 'disabled'}")

    def get_output_state(self, channel: int = 1) -> bool:
        """Mock get output state."""
        self._validate_channel(channel)
        return self._mock_states[channel]["output_enabled"]

    def set_phase(self, phase: float, channel: int = 1) -> None:
        """Mock set phase."""
        self._validate_channel(channel)
        self._mock_states[channel]["phase"] = phase

    def get_phase(self, channel: int = 1) -> float:
        """Mock get phase."""
        self._validate_channel(channel)
        return self._mock_states[channel]["phase"]

    def set_duty_cycle(self, duty_cycle: float, channel: int = 1) -> None:
        """Mock set duty cycle."""
        self._validate_channel(channel)
        self._mock_states[channel]["duty_cycle"] = duty_cycle

    def get_duty_cycle(self, channel: int = 1) -> float:
        """Mock get duty cycle."""
        self._validate_channel(channel)
        return self._mock_states[channel]["duty_cycle"]

    def reset(self) -> None:
        """Mock reset - reset all channels to default state."""
        for ch in range(1, self._num_channels + 1):
            self._mock_states[ch].update({
                "waveform": "SIN",
                "frequency": 1000.0,
                "amplitude": 1.0,
                "offset": 0.0,
                "phase": 0.0,
                "duty_cycle": 50.0,
                "output_enabled": False,
            })
        self._logger.debug("Mock function generator reset")

    def self_test(self) -> bool:
        """Mock self test - always passes."""
        return True

    def get_error_queue(self) -> list:
        """Mock error queue - no errors."""
        return []
