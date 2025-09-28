"""Driver for Keysight InfiniiVision DSOX1000 Series Digital Oscilloscopes."""

import time
from typing import Dict, List, Optional, Any
import numpy as np

from ..interfaces import Oscilloscope, CommunicationError
from ..visa_instrument import VisaInstrument


class KeysightDSOX1000Series(VisaInstrument, Oscilloscope):
    """
    Driver for Keysight InfiniiVision DSOX1000 Series Oscilloscopes.

    Supports models: DSOX1102G, DSOX1204G, etc.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 10000):
        """
        Initialize the oscilloscope driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds
        """
        super().__init__(address, timeout)
        self._model_name = ""
        self._serial_number = ""
        self._num_channels = 4  # Will be determined from model

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the oscilloscope and initialize."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

            # Determine number of channels based on model
            if "1102" in self._model_name:
                self._num_channels = 2
            elif "1204" in self._model_name:
                self._num_channels = 4
            else:
                self._num_channels = 4  # Default

        # Initialize the oscilloscope
        self.reset()
        # Set up for remote operation
        self._write(":SYSTem:HEADer OFF")  # Turn off headers in responses
        self._write(":SYSTem:LONGform OFF")  # Use short form commands

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
        """Return the number of input channels."""
        return self._num_channels

    def _validate_channel(self, channel: int) -> None:
        """Validate channel number is within range."""
        if not 1 <= channel <= self._num_channels:
            raise ValueError(f"Channel {channel} invalid. Valid range: 1-{self._num_channels}")

    def set_channel_state(self, channel: int, enabled: bool) -> None:
        """Enable or disable a channel."""
        self._validate_channel(channel)
        state = "ON" if enabled else "OFF"
        self._write(f":CHANnel{channel}:DISPlay {state}")

    def get_channel_state(self, channel: int) -> bool:
        """Get the state of a channel."""
        self._validate_channel(channel)
        response = self._query(f":CHANnel{channel}:DISPlay?")
        return response.strip() == "1"

    def set_vertical_scale(self, channel: int, scale: float) -> None:
        """Set the vertical scale for a channel."""
        self._validate_channel(channel)
        self._write(f":CHANnel{channel}:SCALe {scale}")

    def get_vertical_scale(self, channel: int) -> float:
        """Get the vertical scale for a channel."""
        self._validate_channel(channel)
        response = self._query(f":CHANnel{channel}:SCALe?")
        return float(response)

    def set_vertical_offset(self, channel: int, offset: float) -> None:
        """Set the vertical offset for a channel."""
        self._validate_channel(channel)
        self._write(f":CHANnel{channel}:OFFSet {offset}")

    def get_vertical_offset(self, channel: int) -> float:
        """Get the vertical offset for a channel."""
        self._validate_channel(channel)
        response = self._query(f":CHANnel{channel}:OFFSet?")
        return float(response)

    def set_time_scale(self, scale: float) -> None:
        """Set the horizontal time scale."""
        self._write(f":TIMebase:SCALe {scale}")

    def get_time_scale(self) -> float:
        """Get the horizontal time scale."""
        response = self._query(":TIMebase:SCALe?")
        return float(response)

    def set_time_offset(self, offset: float) -> None:
        """Set the horizontal time offset."""
        self._write(f":TIMebase:POSition {offset}")

    def get_time_offset(self) -> float:
        """Get the horizontal time offset."""
        response = self._query(":TIMebase:POSition?")
        return float(response)

    def set_trigger_source(self, source: str) -> None:
        """Set the trigger source."""
        valid_sources = ["CHANnel1", "CHANnel2", "CHANnel3", "CHANnel4", "EXTernal", "LINE"]
        if source.upper() not in [s.upper() for s in valid_sources]:
            raise ValueError(f"Invalid trigger source: {source}. Valid sources: {valid_sources}")
        self._write(f":TRIGger:EDGE:SOURce {source}")

    def get_trigger_source(self) -> str:
        """Get the current trigger source."""
        response = self._query(":TRIGger:EDGE:SOURce?")
        return response.strip()

    def set_trigger_level(self, level: float) -> None:
        """Set the trigger level."""
        self._write(f":TRIGger:EDGE:LEVel {level}")

    def get_trigger_level(self) -> float:
        """Get the current trigger level."""
        response = self._query(":TRIGger:EDGE:LEVel?")
        return float(response)

    def set_trigger_edge(self, edge: str) -> None:
        """Set the trigger edge."""
        valid_edges = ["POSitive", "NEGative", "EITHer"]
        if edge.upper() not in [e.upper() for e in valid_edges]:
            raise ValueError(f"Invalid trigger edge: {edge}. Valid edges: {valid_edges}")
        self._write(f":TRIGger:EDGE:SLOPe {edge}")

    def get_trigger_edge(self) -> str:
        """Get the current trigger edge."""
        response = self._query(":TRIGger:EDGE:SLOPe?")
        return response.strip()

    def force_trigger(self) -> None:
        """Force a trigger event."""
        self._write(":TRIGger:FORCe")

    def single_trigger(self) -> None:
        """Set single trigger mode and trigger once."""
        self._write(":TRIGger:SWEep SINGle")
        self._write(":TRIGger:FORCe")

    def auto_trigger(self) -> None:
        """Set auto trigger mode."""
        self._write(":TRIGger:SWEep AUTO")

    def stop_acquisition(self) -> None:
        """Stop acquisition."""
        self._write(":STOP")

    def run_acquisition(self) -> None:
        """Start/run acquisition."""
        self._write(":RUN")

    def acquire_waveform(self, channel: int) -> Dict[str, Any]:
        """
        Acquire waveform data from a channel.

        Args:
            channel: Channel number

        Returns:
            Dictionary containing waveform data
        """
        self._validate_channel(channel)

        # Set data source
        self._write(f":WAVeform:SOURce CHANnel{channel}")

        # Set data format to ASCII for simplicity (could use BYTE for speed)
        self._write(":WAVeform:FORMat ASCii")

        # Get waveform preamble (contains scaling information)
        preamble = self._query(":WAVeform:PREamble?")
        preamble_values = [float(x) for x in preamble.split(',')]

        # Extract scaling parameters
        # Preamble format: FORMAT,TYPE,POINTS,COUNT,XINCREMENT,XORIGIN,XREFERENCE,YINCREMENT,YORIGIN,YREFERENCE
        points = int(preamble_values[2])
        x_increment = preamble_values[4]
        x_origin = preamble_values[5]
        y_increment = preamble_values[7]
        y_origin = preamble_values[8]

        # Get waveform data
        self._write(":WAVeform:DATA?")
        data_response = self._read()

        # Parse ASCII data
        try:
            # Remove any leading/trailing whitespace and split by commas
            data_str = data_response.strip()
            voltage_values = [float(x) for x in data_str.split(',')]
        except ValueError as e:
            raise CommunicationError(f"Failed to parse waveform data: {e}")

        # Create time array
        time_values = [x_origin + i * x_increment for i in range(len(voltage_values))]

        # Convert raw values to actual voltages
        voltage_values = [y_origin + val * y_increment for val in voltage_values]

        return {
            "time": time_values,
            "voltage": voltage_values,
            "sample_rate": 1.0 / x_increment if x_increment > 0 else 0,
            "record_length": len(voltage_values),
            "x_increment": x_increment,
            "y_increment": y_increment,
            "channel": channel
        }

    def measure_parameter(self, channel: int, parameter: str) -> float:
        """
        Measure a waveform parameter.

        Args:
            channel: Channel number
            parameter: Parameter name

        Returns:
            Measured parameter value
        """
        self._validate_channel(channel)

        # Map common parameter names to SCPI commands
        param_map = {
            "FREQ": "FREQuency",
            "FREQUENCY": "FREQuency",
            "AMPL": "VAMPlitude",
            "AMPLITUDE": "VAMPlitude",
            "MEAN": "VAVerage",
            "AVERAGE": "VAVerage",
            "RMS": "VRMS",
            "VRMS": "VRMS",
            "VPP": "VPP",
            "VMAX": "VMAX",
            "VMIN": "VMIN",
            "PERIOD": "PERiod",
            "RISE": "RISetime",
            "FALL": "FALLtime",
            "WIDTH": "PWIDth",
            "DUTY": "DUTYcycle"
        }

        scpi_param = param_map.get(parameter.upper(), parameter)

        # Make measurement
        self._write(f":MEASure:SOURce CHANnel{channel}")
        response = self._query(f":MEASure:{scpi_param}?")

        try:
            return float(response)
        except ValueError:
            # Some measurements might return "9.9E+37" for invalid/unmeasurable
            if "9.9E+37" in response or "OVER" in response.upper():
                raise CommunicationError(f"Parameter {parameter} could not be measured on channel {channel}")
            raise CommunicationError(f"Invalid measurement response: {response}")

    def autoscale(self) -> None:
        """Perform autoscale to automatically set optimal viewing parameters."""
        self._write(":AUToscale")
        # Autoscale can take some time, wait for completion
        self.wait_for_completion(timeout=10.0)

    def clear_display(self) -> None:
        """Clear the display."""
        self._write(":DISPlay:CLEar")

    def save_screen(self, filename: str, format: str = "PNG") -> None:
        """
        Save screen image to file.

        Args:
            filename: Filename to save (without extension)
            format: Image format ("PNG", "BMP", "JPEG")
        """
        valid_formats = ["PNG", "BMP", "JPEG"]
        if format.upper() not in valid_formats:
            raise ValueError(f"Invalid format: {format}. Valid formats: {valid_formats}")

        self._write(f":DISPlay:DATA? {format.upper()}")
        image_data = self._query_binary(":DISPlay:DATA?")

        with open(f"{filename}.{format.lower()}", "wb") as f:
            f.write(image_data)


class MockDSOX1000Series(KeysightDSOX1000Series):
    """Mock version of Keysight DSOX1000 Series for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 10000, model: str = "DSOX1204G"):
        """Initialize mock oscilloscope."""
        super().__init__(address, timeout)
        self._mock_model = model
        self._mock_states: Dict[str, Any] = {}
        self._init_mock_states()

    def _init_mock_states(self) -> None:
        """Initialize mock internal states."""
        # Set number of channels based on model
        if "1102" in self._mock_model:
            self._num_channels = 2
        elif "1204" in self._mock_model:
            self._num_channels = 4
        else:
            self._num_channels = 4

        # Channel states
        for ch in range(1, self._num_channels + 1):
            self._mock_states[f"ch{ch}_display"] = True
            self._mock_states[f"ch{ch}_scale"] = 1.0  # 1V/div
            self._mock_states[f"ch{ch}_offset"] = 0.0

        # Timebase
        self._mock_states["time_scale"] = 1e-3  # 1ms/div
        self._mock_states["time_offset"] = 0.0

        # Trigger
        self._mock_states["trigger_source"] = "CHANnel1"
        self._mock_states["trigger_level"] = 0.0
        self._mock_states["trigger_edge"] = "POSitive"

    @property
    def is_connected(self) -> bool:
        """Return mock connection status."""
        return getattr(self, '_connected', False)

    def connect(self, address: Optional[str] = None) -> None:
        """Mock connection."""
        if address:
            self.address = address
        if not self.address:
            self.address = "MOCK::DSOX1204G"

        self._connected = True
        self._model_name = self._mock_model
        self._serial_number = "MOCK123456"
        self._logger.info(f"Mock {self._mock_model} connected at {self.address}")

    def _write(self, command: str) -> None:
        """Mock VISA write operation."""
        # Just log the command, don't actually try to write
        self._logger.debug(f"Mock VISA write: {command}")

    def _query(self, command: str) -> str:
        """Mock VISA query operation."""
        # Return mock responses for common queries
        if "CHANnel" in command and "DISPlay?" in command:
            return "1"
        elif "SCALe?" in command:
            return "1.0"
        elif "OFFSet?" in command:
            return "0.0"
        return "MOCK_RESPONSE"

    def set_channel_state(self, channel: int, enabled: bool) -> None:
        """Mock set channel state."""
        self._validate_channel(channel)
        self._mock_states[f"ch{channel}_display"] = enabled

    def get_channel_state(self, channel: int) -> bool:
        """Mock get channel state."""
        self._validate_channel(channel)
        return self._mock_states.get(f"ch{channel}_display", True)

    def acquire_waveform(self, channel: int) -> Dict[str, Any]:
        """Mock waveform acquisition - generates sine wave."""
        self._validate_channel(channel)

        # Generate mock sine wave data
        sample_rate = 1e6  # 1 MHz
        duration = 10e-3   # 10 ms
        frequency = 1000   # 1 kHz sine wave
        amplitude = 1.0    # 1V amplitude

        num_points = int(sample_rate * duration)
        time_values = [i / sample_rate for i in range(num_points)]
        voltage_values = [amplitude * np.sin(2 * np.pi * frequency * t) for t in time_values]

        return {
            "time": time_values,
            "voltage": voltage_values,
            "sample_rate": sample_rate,
            "record_length": num_points,
            "x_increment": 1.0 / sample_rate,
            "y_increment": amplitude / 32768,  # Simulate 16-bit ADC
            "channel": channel
        }

    def measure_parameter(self, channel: int, parameter: str) -> float:
        """Mock parameter measurement."""
        self._validate_channel(channel)

        # Return realistic values for common parameters
        mock_measurements = {
            "FREQ": 1000.0,      # 1 kHz
            "FREQUENCY": 1000.0,
            "AMPL": 2.0,         # 2V p-p
            "AMPLITUDE": 2.0,
            "MEAN": 0.0,         # 0V DC offset
            "AVERAGE": 0.0,
            "RMS": 0.707,        # RMS of 1V sine wave
            "VRMS": 0.707,
            "VPP": 2.0,          # 2V peak-to-peak
            "VMAX": 1.0,         # +1V peak
            "VMIN": -1.0,        # -1V peak
            "PERIOD": 1e-3,      # 1ms period
        }

        return mock_measurements.get(parameter.upper(), 0.0)

    def reset(self) -> None:
        """Mock reset."""
        self._init_mock_states()
        self._logger.debug("Mock oscilloscope reset")

    def self_test(self) -> bool:
        """Mock self test."""
        return True

    def get_error_queue(self) -> List[str]:
        """Mock error queue."""
        return []