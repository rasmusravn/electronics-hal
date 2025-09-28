"""Abstract base classes defining instrument interfaces for the HAL."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class InstrumentError(Exception):
    """Base exception for instrument-related errors."""


class CommunicationError(InstrumentError):
    """Raised when communication with an instrument fails."""


class InstrumentInterface(ABC):
    """Base interface that all instruments must implement."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the instrument's model identifier."""

    @property
    @abstractmethod
    def serial_number(self) -> str:
        """Return the instrument's unique serial number."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if the instrument is connected and responsive."""

    @abstractmethod
    def connect(self, address: str) -> None:
        """
        Establish connection to the instrument.

        Args:
            address: VISA address string for the instrument

        Raises:
            CommunicationError: If connection fails
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the instrument."""

    @abstractmethod
    def reset(self) -> None:
        """Send a reset command (*RST) to the instrument."""

    @abstractmethod
    def self_test(self) -> bool:
        """
        Perform instrument self-test.

        Returns:
            True if self-test passes, False otherwise
        """

    @abstractmethod
    def get_error_queue(self) -> List[str]:
        """
        Read and clear the instrument's error queue.

        Returns:
            List of error messages from the instrument
        """


class PowerSupply(InstrumentInterface):
    """Interface for programmable power supplies."""

    @abstractmethod
    def set_voltage(self, voltage: float, channel: int = 1) -> None:
        """
        Set the output voltage for a channel.

        Args:
            voltage: Target voltage in volts
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_voltage(self, channel: int = 1) -> float:
        """
        Get the current voltage setting for a channel.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current voltage setting in volts
        """

    @abstractmethod
    def measure_voltage(self, channel: int = 1) -> float:
        """
        Measure the actual output voltage for a channel.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Measured voltage in volts
        """

    @abstractmethod
    def set_current_limit(self, current: float, channel: int = 1) -> None:
        """
        Set the current limit for a channel.

        Args:
            current: Current limit in amperes
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_current_limit(self, channel: int = 1) -> float:
        """
        Get the current limit setting for a channel.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current limit in amperes
        """

    @abstractmethod
    def measure_current(self, channel: int = 1) -> float:
        """
        Measure the actual output current for a channel.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Measured current in amperes
        """

    @abstractmethod
    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """
        Enable or disable the output for a channel.

        Args:
            enabled: True to enable output, False to disable
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_output_state(self, channel: int = 1) -> bool:
        """
        Get the output state for a channel.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            True if output is enabled, False if disabled
        """

    @abstractmethod
    def set_ovp_threshold(self, threshold: float, channel: int = 1) -> None:
        """
        Set the over-voltage protection threshold.

        Args:
            threshold: OVP threshold in volts
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_ovp_threshold(self, channel: int = 1) -> float:
        """
        Get the over-voltage protection threshold.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            OVP threshold in volts
        """


class DigitalMultimeter(InstrumentInterface):
    """Interface for digital multimeters."""

    @abstractmethod
    def measure_dc_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform a DC voltage measurement.

        Args:
            range: Measurement range in volts (None for auto-range)
            resolution: Measurement resolution in volts (None for default)

        Returns:
            Measured DC voltage in volts
        """

    @abstractmethod
    def measure_ac_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform an AC voltage measurement.

        Args:
            range: Measurement range in volts (None for auto-range)
            resolution: Measurement resolution in volts (None for default)

        Returns:
            Measured AC voltage in volts RMS
        """

    @abstractmethod
    def measure_dc_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform a DC current measurement.

        Args:
            range: Measurement range in amperes (None for auto-range)
            resolution: Measurement resolution in amperes (None for default)

        Returns:
            Measured DC current in amperes
        """

    @abstractmethod
    def measure_ac_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform an AC current measurement.

        Args:
            range: Measurement range in amperes (None for auto-range)
            resolution: Measurement resolution in amperes (None for default)

        Returns:
            Measured AC current in amperes RMS
        """

    @abstractmethod
    def measure_resistance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform a resistance measurement.

        Args:
            range: Measurement range in ohms (None for auto-range)
            resolution: Measurement resolution in ohms (None for default)

        Returns:
            Measured resistance in ohms
        """

    @abstractmethod
    def measure_capacitance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """
        Perform a capacitance measurement.

        Args:
            range: Measurement range in farads (None for auto-range)
            resolution: Measurement resolution in farads (None for default)

        Returns:
            Measured capacitance in farads
        """

    @abstractmethod
    def configure_measurement(self, function: str, range: Optional[float] = None, resolution: Optional[float] = None) -> None:
        """
        Configure the DMM for a specific measurement without triggering.

        Args:
            function: Measurement function ('VDC', 'VAC', 'IDC', 'IAC', 'RES', 'CAP', etc.)
            range: Measurement range (None for auto-range)
            resolution: Measurement resolution (None for default)
        """

    @abstractmethod
    def trigger_measurement(self) -> None:
        """Trigger a measurement using the current configuration."""

    @abstractmethod
    def read_measurement(self) -> float:
        """
        Read the result of a previously triggered measurement.

        Returns:
            Measurement result in appropriate units
        """


class FunctionGenerator(InstrumentInterface):
    """Interface for function/waveform generators."""

    @abstractmethod
    def set_waveform(self, waveform: str, channel: int = 1) -> None:
        """
        Set the output waveform type.

        Args:
            waveform: Waveform type ('SIN', 'SQU', 'TRI', 'RAMP', 'NOISE', etc.)
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_waveform(self, channel: int = 1) -> str:
        """
        Get the current waveform type.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current waveform type
        """

    @abstractmethod
    def set_frequency(self, frequency: float, channel: int = 1) -> None:
        """
        Set the output frequency.

        Args:
            frequency: Frequency in hertz
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_frequency(self, channel: int = 1) -> float:
        """
        Get the current frequency setting.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current frequency in hertz
        """

    @abstractmethod
    def set_amplitude(self, amplitude: float, channel: int = 1) -> None:
        """
        Set the output amplitude.

        Args:
            amplitude: Amplitude in volts peak-to-peak
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_amplitude(self, channel: int = 1) -> float:
        """
        Get the current amplitude setting.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current amplitude in volts peak-to-peak
        """

    @abstractmethod
    def set_offset(self, offset: float, channel: int = 1) -> None:
        """
        Set the DC offset.

        Args:
            offset: DC offset in volts
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_offset(self, channel: int = 1) -> float:
        """
        Get the current DC offset setting.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            Current DC offset in volts
        """

    @abstractmethod
    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """
        Enable or disable the output.

        Args:
            enabled: True to enable output, False to disable
            channel: Output channel number (default: 1)
        """

    @abstractmethod
    def get_output_state(self, channel: int = 1) -> bool:
        """
        Get the output state.

        Args:
            channel: Output channel number (default: 1)

        Returns:
            True if output is enabled, False if disabled
        """


class Oscilloscope(InstrumentInterface):
    """Interface for digital oscilloscopes."""

    @abstractmethod
    def set_channel_state(self, channel: int, enabled: bool) -> None:
        """
        Enable or disable a channel.

        Args:
            channel: Channel number
            enabled: True to enable, False to disable
        """

    @abstractmethod
    def get_channel_state(self, channel: int) -> bool:
        """
        Get the state of a channel.

        Args:
            channel: Channel number

        Returns:
            True if enabled, False if disabled
        """

    @abstractmethod
    def set_vertical_scale(self, channel: int, scale: float) -> None:
        """
        Set the vertical scale for a channel.

        Args:
            channel: Channel number
            scale: Vertical scale in volts per division
        """

    @abstractmethod
    def get_vertical_scale(self, channel: int) -> float:
        """
        Get the vertical scale for a channel.

        Args:
            channel: Channel number

        Returns:
            Vertical scale in volts per division
        """

    @abstractmethod
    def set_time_scale(self, scale: float) -> None:
        """
        Set the horizontal time scale.

        Args:
            scale: Time scale in seconds per division
        """

    @abstractmethod
    def get_time_scale(self) -> float:
        """
        Get the horizontal time scale.

        Returns:
            Time scale in seconds per division
        """

    @abstractmethod
    def set_trigger_source(self, source: str) -> None:
        """
        Set the trigger source.

        Args:
            source: Trigger source ('CH1', 'CH2', 'EXT', etc.)
        """

    @abstractmethod
    def set_trigger_level(self, level: float) -> None:
        """
        Set the trigger level.

        Args:
            level: Trigger level in volts
        """

    @abstractmethod
    def set_trigger_edge(self, edge: str) -> None:
        """
        Set the trigger edge.

        Args:
            edge: Trigger edge ('RISING', 'FALLING', 'EITHER')
        """

    @abstractmethod
    def force_trigger(self) -> None:
        """Force a trigger event."""

    @abstractmethod
    def acquire_waveform(self, channel: int) -> Dict[str, Any]:
        """
        Acquire waveform data from a channel.

        Args:
            channel: Channel number

        Returns:
            Dictionary containing waveform data with keys:
            - 'time': Time values array
            - 'voltage': Voltage values array
            - 'sample_rate': Sample rate in Hz
            - 'record_length': Number of samples
        """

    @abstractmethod
    def measure_parameter(self, channel: int, parameter: str) -> float:
        """
        Measure a waveform parameter.

        Args:
            channel: Channel number
            parameter: Parameter name ('FREQ', 'AMPL', 'MEAN', 'RMS', etc.)

        Returns:
            Measured parameter value
        """


class SignalAnalyzer(InstrumentInterface):
    """Interface for signal and spectrum analyzers."""

    @abstractmethod
    def set_frequency_span(self, span: float) -> None:
        """
        Set the frequency span.

        Args:
            span: Frequency span in Hz
        """

    @abstractmethod
    def get_frequency_span(self) -> float:
        """
        Get the current frequency span.

        Returns:
            Frequency span in Hz
        """

    @abstractmethod
    def set_center_frequency(self, frequency: float) -> None:
        """
        Set the center frequency.

        Args:
            frequency: Center frequency in Hz
        """

    @abstractmethod
    def get_center_frequency(self) -> float:
        """
        Get the current center frequency.

        Returns:
            Center frequency in Hz
        """

    @abstractmethod
    def set_start_frequency(self, frequency: float) -> None:
        """
        Set the start frequency.

        Args:
            frequency: Start frequency in Hz
        """

    @abstractmethod
    def get_start_frequency(self) -> float:
        """
        Get the current start frequency.

        Returns:
            Start frequency in Hz
        """

    @abstractmethod
    def set_stop_frequency(self, frequency: float) -> None:
        """
        Set the stop frequency.

        Args:
            frequency: Stop frequency in Hz
        """

    @abstractmethod
    def get_stop_frequency(self) -> float:
        """
        Get the current stop frequency.

        Returns:
            Stop frequency in Hz
        """

    @abstractmethod
    def set_resolution_bandwidth(self, bandwidth: float) -> None:
        """
        Set the resolution bandwidth.

        Args:
            bandwidth: Resolution bandwidth in Hz
        """

    @abstractmethod
    def get_resolution_bandwidth(self) -> float:
        """
        Get the current resolution bandwidth.

        Returns:
            Resolution bandwidth in Hz
        """

    @abstractmethod
    def set_video_bandwidth(self, bandwidth: float) -> None:
        """
        Set the video bandwidth.

        Args:
            bandwidth: Video bandwidth in Hz
        """

    @abstractmethod
    def get_video_bandwidth(self) -> float:
        """
        Get the current video bandwidth.

        Returns:
            Video bandwidth in Hz
        """

    @abstractmethod
    def set_reference_level(self, level: float) -> None:
        """
        Set the reference level.

        Args:
            level: Reference level in dBm
        """

    @abstractmethod
    def get_reference_level(self) -> float:
        """
        Get the current reference level.

        Returns:
            Reference level in dBm
        """

    @abstractmethod
    def set_attenuation(self, attenuation: float) -> None:
        """
        Set the input attenuation.

        Args:
            attenuation: Attenuation in dB
        """

    @abstractmethod
    def get_attenuation(self) -> float:
        """
        Get the current input attenuation.

        Returns:
            Attenuation in dB
        """

    @abstractmethod
    def acquire_trace(self, trace_number: int = 1) -> Dict[str, Any]:
        """
        Acquire a trace from the analyzer.

        Args:
            trace_number: Trace number to acquire

        Returns:
            Dictionary containing frequency and amplitude data
        """

    @abstractmethod
    def measure_peak(self, trace_number: int = 1) -> Dict[str, float]:
        """
        Measure the peak in a trace.

        Args:
            trace_number: Trace number to analyze

        Returns:
            Dictionary with 'frequency' and 'amplitude' keys
        """

    @abstractmethod
    def measure_marker(self, marker_number: int, frequency: float) -> float:
        """
        Set a marker and read its amplitude.

        Args:
            marker_number: Marker number (1-6 typically)
            frequency: Frequency to place marker at

        Returns:
            Amplitude at marker frequency in dBm
        """

    @abstractmethod
    def auto_tune(self) -> None:
        """Perform auto-tune to optimize settings for current signal."""
