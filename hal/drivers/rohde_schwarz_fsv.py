"""Driver for Rohde & Schwarz FSV Signal and Spectrum Analyzer."""

import time
from typing import Dict, List, Optional, Any
import numpy as np

from ..interfaces import SignalAnalyzer, CommunicationError
from ..visa_instrument import VisaInstrument


class RohdeSchwarzFSV(VisaInstrument, SignalAnalyzer):
    """
    Driver for Rohde & Schwarz FSV Signal and Spectrum Analyzer.

    The FSV is a versatile signal and spectrum analyzer series offering
    excellent price-performance ratio for various applications.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 10000, retry_config=None):
        """
        Initialize the FSV driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds
            retry_config: Retry configuration for communication
        """
        super().__init__(address, timeout, retry_config)
        self._model_name = ""
        self._serial_number = ""
        self._frequency_range = (10, 40e9)  # 10 Hz to 40 GHz typical for FSV

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the analyzer and initialize."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

            # Adjust frequency range based on model
            if "FSV7" in self._model_name:
                self._frequency_range = (10, 7e9)
            elif "FSV13" in self._model_name:
                self._frequency_range = (10, 13.6e9)
            elif "FSV30" in self._model_name:
                self._frequency_range = (10, 30e9)
            elif "FSV40" in self._model_name:
                self._frequency_range = (10, 40e9)

        # Initialize the analyzer
        self.reset()
        # Set up for remote operation
        self._write("SYST:DISP:UPD ON")  # Enable display updates
        self._write("INIT:CONT OFF")     # Set single sweep mode initially

    @property
    def model_name(self) -> str:
        """Return the instrument's model name."""
        return self._model_name

    @property
    def serial_number(self) -> str:
        """Return the instrument's serial number."""
        return self._serial_number

    @property
    def frequency_range(self) -> tuple:
        """Return the frequency range (min, max) in Hz."""
        return self._frequency_range

    def set_frequency_span(self, span: float) -> None:
        """Set the frequency span."""
        if span <= 0:
            raise ValueError("Frequency span must be positive")
        self._write(f"FREQ:SPAN {span}")

    def get_frequency_span(self) -> float:
        """Get the current frequency span."""
        response = self._query("FREQ:SPAN?")
        return float(response)

    def set_center_frequency(self, frequency: float) -> None:
        """Set the center frequency."""
        if not (self._frequency_range[0] <= frequency <= self._frequency_range[1]):
            raise ValueError(f"Frequency {frequency} outside valid range {self._frequency_range}")
        self._write(f"FREQ:CENT {frequency}")

    def get_center_frequency(self) -> float:
        """Get the current center frequency."""
        response = self._query("FREQ:CENT?")
        return float(response)

    def set_start_frequency(self, frequency: float) -> None:
        """Set the start frequency."""
        if not (self._frequency_range[0] <= frequency <= self._frequency_range[1]):
            raise ValueError(f"Frequency {frequency} outside valid range {self._frequency_range}")
        self._write(f"FREQ:STAR {frequency}")

    def get_start_frequency(self) -> float:
        """Get the current start frequency."""
        response = self._query("FREQ:STAR?")
        return float(response)

    def set_stop_frequency(self, frequency: float) -> None:
        """Set the stop frequency."""
        if not (self._frequency_range[0] <= frequency <= self._frequency_range[1]):
            raise ValueError(f"Frequency {frequency} outside valid range {self._frequency_range}")
        self._write(f"FREQ:STOP {frequency}")

    def get_stop_frequency(self) -> float:
        """Get the current stop frequency."""
        response = self._query("FREQ:STOP?")
        return float(response)

    def set_resolution_bandwidth(self, bandwidth: float) -> None:
        """Set the resolution bandwidth."""
        if bandwidth <= 0:
            raise ValueError("Resolution bandwidth must be positive")
        self._write(f"SENS:BAND:RES {bandwidth}")

    def get_resolution_bandwidth(self) -> float:
        """Get the current resolution bandwidth."""
        response = self._query("SENS:BAND:RES?")
        return float(response)

    def set_video_bandwidth(self, bandwidth: float) -> None:
        """Set the video bandwidth."""
        if bandwidth <= 0:
            raise ValueError("Video bandwidth must be positive")
        self._write(f"SENS:BAND:VID {bandwidth}")

    def get_video_bandwidth(self) -> float:
        """Get the current video bandwidth."""
        response = self._query("SENS:BAND:VID?")
        return float(response)

    def set_reference_level(self, level: float) -> None:
        """Set the reference level."""
        self._write(f"DISP:WIND:TRAC:Y:RLEV {level}")

    def get_reference_level(self) -> float:
        """Get the current reference level."""
        response = self._query("DISP:WIND:TRAC:Y:RLEV?")
        return float(response)

    def set_attenuation(self, attenuation: float) -> None:
        """Set the input attenuation."""
        if attenuation < 0:
            raise ValueError("Attenuation cannot be negative")
        self._write(f"INP:ATT {attenuation}")

    def get_attenuation(self) -> float:
        """Get the current input attenuation."""
        response = self._query("INP:ATT?")
        return float(response)

    def set_sweep_mode(self, mode: str) -> None:
        """
        Set the sweep mode.

        Args:
            mode: 'CONT' (continuous), 'SING' (single)
        """
        if mode.upper() not in ["CONT", "CONTINUOUS", "SING", "SINGLE"]:
            raise ValueError(f"Invalid sweep mode: {mode}. Valid modes: CONT, SING")

        if mode.upper() in ["CONT", "CONTINUOUS"]:
            self._write("INIT:CONT ON")
        else:
            self._write("INIT:CONT OFF")

    def trigger_sweep(self) -> None:
        """Trigger a single sweep."""
        self._write("INIT")

    def wait_for_sweep(self, timeout: float = 30.0) -> None:
        """
        Wait for sweep to complete.

        Args:
            timeout: Maximum time to wait in seconds
        """
        self.wait_for_completion(timeout)

    def acquire_trace(self, trace_number: int = 1) -> Dict[str, Any]:
        """
        Acquire a trace from the analyzer.

        Args:
            trace_number: Trace number to acquire (1-6 typically)

        Returns:
            Dictionary containing frequency and amplitude data
        """
        if not 1 <= trace_number <= 6:
            raise ValueError("Trace number must be between 1 and 6")

        # Trigger a sweep and wait for completion
        self.trigger_sweep()
        self.wait_for_sweep()

        # Get trace data
        trace_data = self._query(f"TRAC? TRACE{trace_number}")

        # Parse the data (comma-separated values)
        try:
            amplitude_values = [float(x) for x in trace_data.split(',')]
        except ValueError as e:
            raise CommunicationError(f"Failed to parse trace data: {e}")

        # Get frequency information
        start_freq = self.get_start_frequency()
        stop_freq = self.get_stop_frequency()
        num_points = len(amplitude_values)

        # Generate frequency array
        frequency_values = np.linspace(start_freq, stop_freq, num_points).tolist()

        return {
            "frequency": frequency_values,
            "amplitude": amplitude_values,
            "trace_number": trace_number,
            "start_frequency": start_freq,
            "stop_frequency": stop_freq,
            "num_points": num_points,
            "reference_level": self.get_reference_level(),
            "resolution_bandwidth": self.get_resolution_bandwidth()
        }

    def measure_peak(self, trace_number: int = 1) -> Dict[str, float]:
        """
        Measure the peak in a trace.

        Args:
            trace_number: Trace number to analyze

        Returns:
            Dictionary with 'frequency' and 'amplitude' keys
        """
        if not 1 <= trace_number <= 6:
            raise ValueError("Trace number must be between 1 and 6")

        # Set trace for peak search
        self._write(f"CALC:MARK:TRAC {trace_number}")

        # Perform peak search
        self._write("CALC:MARK:MAX")

        # Read peak frequency and amplitude
        freq_response = self._query("CALC:MARK:X?")
        ampl_response = self._query("CALC:MARK:Y?")

        return {
            "frequency": float(freq_response),
            "amplitude": float(ampl_response)
        }

    def measure_marker(self, marker_number: int, frequency: float) -> float:
        """
        Set a marker and read its amplitude.

        Args:
            marker_number: Marker number (1-4 for FSV)
            frequency: Frequency to place marker at

        Returns:
            Amplitude at marker frequency in dBm
        """
        if not 1 <= marker_number <= 4:
            raise ValueError("Marker number must be between 1 and 4 for FSV")

        # Set marker frequency
        self._write(f"CALC:MARK{marker_number}:X {frequency}")

        # Enable marker if not already enabled
        self._write(f"CALC:MARK{marker_number}:STAT ON")

        # Read marker amplitude
        response = self._query(f"CALC:MARK{marker_number}:Y?")
        return float(response)

    def set_marker_delta_mode(self, marker_number: int, reference_marker: int = 1) -> None:
        """
        Set a marker to delta mode relative to reference marker.

        Args:
            marker_number: Marker to set as delta
            reference_marker: Reference marker for delta measurement
        """
        if not 1 <= marker_number <= 4 or not 1 <= reference_marker <= 4:
            raise ValueError("Marker numbers must be between 1 and 4")

        self._write(f"CALC:DELT{marker_number}:STAT ON")
        self._write(f"CALC:DELT{marker_number}:LINK {reference_marker}")

    def auto_tune(self) -> None:
        """Perform auto-tune to optimize settings for current signal."""
        self._write("SENS:ADJ:ALL")
        # Auto-tune can take some time
        self.wait_for_completion(timeout=30.0)

    def set_detector_mode(self, mode: str) -> None:
        """
        Set the detector mode.

        Args:
            mode: 'AUTO', 'PEAK', 'AVER' (average), 'NORM' (normal), 'SAMP' (sample)
        """
        valid_modes = ["AUTO", "PEAK", "AVER", "AVERAGE", "NORM", "NORMAL", "SAMP", "SAMPLE"]
        if mode.upper() not in valid_modes:
            raise ValueError(f"Invalid detector mode: {mode}. Valid modes: {valid_modes}")

        # Map to SCPI commands
        mode_map = {
            "AUTO": "AUTO",
            "PEAK": "POS",
            "AVER": "AVER",
            "AVERAGE": "AVER",
            "NORM": "NORM",
            "NORMAL": "NORM",
            "SAMP": "SAMP",
            "SAMPLE": "SAMP"
        }

        scpi_mode = mode_map[mode.upper()]
        self._write(f"SENS:DET {scpi_mode}")

    def set_trace_mode(self, trace_number: int, mode: str) -> None:
        """
        Set the trace mode.

        Args:
            trace_number: Trace number (1-6)
            mode: 'WRIT' (write), 'AVER' (average), 'MAXH' (max hold), 'MINH' (min hold)
        """
        if not 1 <= trace_number <= 6:
            raise ValueError("Trace number must be between 1 and 6")

        valid_modes = ["WRIT", "WRITE", "AVER", "AVERAGE", "MAXH", "MAXHOLD", "MINH", "MINHOLD"]
        if mode.upper() not in valid_modes:
            raise ValueError(f"Invalid trace mode: {mode}. Valid modes: {valid_modes}")

        # Map to SCPI commands
        mode_map = {
            "WRIT": "WRIT",
            "WRITE": "WRIT",
            "AVER": "AVER",
            "AVERAGE": "AVER",
            "MAXH": "MAXH",
            "MAXHOLD": "MAXH",
            "MINH": "MINH",
            "MINHOLD": "MINH"
        }

        scpi_mode = mode_map[mode.upper()]
        self._write(f"DISP:WIND:TRAC{trace_number}:MODE {scpi_mode}")

    def set_sweep_points(self, points: int) -> None:
        """
        Set the number of sweep points.

        Args:
            points: Number of sweep points (typically 101-32001)
        """
        if points < 101 or points > 32001:
            raise ValueError("Sweep points must be between 101 and 32001")
        self._write(f"SENS:SWE:POIN {points}")

    def get_sweep_points(self) -> int:
        """Get the current number of sweep points."""
        response = self._query("SENS:SWE:POIN?")
        return int(float(response))

    def set_sweep_time(self, time_seconds: float) -> None:
        """
        Set the sweep time.

        Args:
            time_seconds: Sweep time in seconds
        """
        if time_seconds <= 0:
            raise ValueError("Sweep time must be positive")
        self._write(f"SENS:SWE:TIME {time_seconds}")

    def get_sweep_time(self) -> float:
        """Get the current sweep time."""
        response = self._query("SENS:SWE:TIME?")
        return float(response)

    def get_instrument_status(self) -> Dict[str, Any]:
        """
        Get comprehensive instrument status.

        Returns:
            Dictionary containing current settings and status
        """
        try:
            status = {
                "model": self.model_name,
                "serial": self.serial_number,
                "connected": self.is_connected,
                "center_frequency": self.get_center_frequency(),
                "frequency_span": self.get_frequency_span(),
                "start_frequency": self.get_start_frequency(),
                "stop_frequency": self.get_stop_frequency(),
                "reference_level": self.get_reference_level(),
                "resolution_bandwidth": self.get_resolution_bandwidth(),
                "video_bandwidth": self.get_video_bandwidth(),
                "attenuation": self.get_attenuation(),
                "sweep_points": self.get_sweep_points(),
                "sweep_time": self.get_sweep_time(),
                "errors": self.get_error_queue()
            }
        except Exception as e:
            status = {"error": str(e)}

        return status


class MockFSV(RohdeSchwarzFSV):
    """Mock version of Rohde & Schwarz FSV for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 10000, retry_config=None, model: str = "FSV30"):
        """Initialize mock FSV."""
        super().__init__(address, timeout, retry_config)
        self._mock_model = model
        self._mock_states: Dict[str, Any] = {}
        self._init_mock_states()

    def _init_mock_states(self) -> None:
        """Initialize mock internal states."""
        self._mock_states = {
            "center_frequency": 1e9,     # 1 GHz
            "frequency_span": 100e6,     # 100 MHz
            "start_frequency": 950e6,    # 950 MHz
            "stop_frequency": 1050e6,    # 1.05 GHz
            "reference_level": 0.0,      # 0 dBm
            "resolution_bandwidth": 1e6,  # 1 MHz
            "video_bandwidth": 3e6,      # 3 MHz
            "attenuation": 10.0,         # 10 dB
            "sweep_points": 1001,
            "sweep_time": 0.1           # 100 ms
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

        # Set frequency range based on model
        if "FSV7" in self._mock_model:
            self._frequency_range = (10, 7e9)
        elif "FSV13" in self._mock_model:
            self._frequency_range = (10, 13.6e9)
        elif "FSV30" in self._mock_model:
            self._frequency_range = (10, 30e9)
        elif "FSV40" in self._mock_model:
            self._frequency_range = (10, 40e9)

        self._logger.info(f"Mock {self._mock_model} connected at {self.address}")

    def _write(self, command: str) -> None:
        """Mock VISA write operation."""
        self._logger.debug(f"Mock VISA write: {command}")

        # Parse common commands and update mock state
        if "FREQ:CENT" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["center_frequency"] = value
        elif "FREQ:SPAN" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["frequency_span"] = value
        elif "FREQ:STAR" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["start_frequency"] = value
        elif "FREQ:STOP" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["stop_frequency"] = value
        elif "DISP:WIND:TRAC:Y:RLEV" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["reference_level"] = value
        elif "SENS:BAND:RES" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["resolution_bandwidth"] = value
        elif "SENS:BAND:VID" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["video_bandwidth"] = value
        elif "SENS:SWE:POIN" in command and "?" not in command:
            value = int(float(command.split()[-1]))
            self._mock_states["sweep_points"] = value

    def _query(self, command: str) -> str:
        """Mock VISA query operation."""
        if "FREQ:CENT?" in command:
            return str(self._mock_states["center_frequency"])
        elif "FREQ:SPAN?" in command:
            return str(self._mock_states["frequency_span"])
        elif "FREQ:STAR?" in command:
            return str(self._mock_states["start_frequency"])
        elif "FREQ:STOP?" in command:
            return str(self._mock_states["stop_frequency"])
        elif "DISP:WIND:TRAC:Y:RLEV?" in command:
            return str(self._mock_states["reference_level"])
        elif "SENS:BAND:RES?" in command:
            return str(self._mock_states["resolution_bandwidth"])
        elif "SENS:BAND:VID?" in command:
            return str(self._mock_states["video_bandwidth"])
        elif "INP:ATT?" in command:
            return str(self._mock_states["attenuation"])
        elif "SENS:SWE:POIN?" in command:
            return str(self._mock_states["sweep_points"])
        elif "SENS:SWE:TIME?" in command:
            return str(self._mock_states["sweep_time"])
        elif "TRAC?" in command:
            # Generate mock spectrum data
            return self._generate_mock_spectrum()
        return "MOCK_RESPONSE"

    def _generate_mock_spectrum(self) -> str:
        """Generate mock spectrum trace data."""
        num_points = self._mock_states["sweep_points"]
        ref_level = self._mock_states["reference_level"]

        # Create a mock spectrum with noise floor and some peaks
        noise_floor = ref_level - 70  # -70 dB below reference
        spectrum = np.random.normal(noise_floor, 1.5, num_points)  # Noise floor

        # Add some mock peaks
        peak_indices = [num_points//3, 2*num_points//3]
        peak_levels = [ref_level - 15, ref_level - 25]

        for idx, level in zip(peak_indices, peak_levels):
            # Add Gaussian peaks
            peak_width = 15
            for i in range(max(0, idx-peak_width), min(num_points, idx+peak_width)):
                distance = abs(i - idx)
                peak_contribution = level * np.exp(-(distance**2)/(2*(peak_width/2.5)**2))
                spectrum[i] = max(spectrum[i], peak_contribution)

        # Convert to comma-separated string
        return ','.join([f"{x:.6f}" for x in spectrum])

    def measure_peak(self, trace_number: int = 1) -> Dict[str, float]:
        """Mock peak measurement."""
        center_freq = self._mock_states["center_frequency"]
        ref_level = self._mock_states["reference_level"]

        # Return a mock peak near center frequency
        return {
            "frequency": center_freq + np.random.uniform(-5e6, 5e6),  # ±5 MHz from center
            "amplitude": ref_level - np.random.uniform(10, 20)  # 10-20 dB below reference
        }

    def measure_marker(self, marker_number: int, frequency: float) -> float:
        """Mock marker measurement."""
        ref_level = self._mock_states["reference_level"]
        # Return amplitude based on distance from center frequency
        center_freq = self._mock_states["center_frequency"]
        freq_offset = abs(frequency - center_freq)

        # Simple model: amplitude decreases with frequency offset
        amplitude = ref_level - 30 * np.log10(1 + freq_offset / 5e6)  # -30 dB per decade

        return amplitude + np.random.uniform(-1, 1)  # Add some noise

    def reset(self) -> None:
        """Mock reset."""
        self._init_mock_states()
        self._logger.debug("Mock FSV reset")

    def self_test(self) -> bool:
        """Mock self test."""
        return True

    def get_error_queue(self) -> List[str]:
        """Mock error queue."""
        return []