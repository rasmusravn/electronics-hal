"""Driver for Rohde & Schwarz SMA100A RF Signal Generator."""

import time
from typing import Dict, List, Optional, Any
import numpy as np

from ..interfaces import FunctionGenerator, CommunicationError
from ..visa_instrument import VisaInstrument


class RohdeSchwarzSMA100A(VisaInstrument, FunctionGenerator):
    """
    Driver for Rohde & Schwarz SMA100A RF Signal Generator.

    The SMA100A is a high-performance analog RF signal generator
    for applications requiring highest spectral purity.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 5000, retry_config=None):
        """
        Initialize the SMA100A driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds
            retry_config: Retry configuration for communication
        """
        super().__init__(address, timeout, retry_config)
        self._model_name = ""
        self._serial_number = ""
        self._frequency_range = (8e3, 20e9)  # 8 kHz to 20 GHz typical
        self._power_range = (-120, 30)       # -120 to +30 dBm typical

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the generator and initialize."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

            # Adjust ranges based on model
            if "SMA100A" in self._model_name:
                if "B20" in self._model_name:
                    self._frequency_range = (8e3, 20e9)
                elif "B31" in self._model_name:
                    self._frequency_range = (8e3, 31.8e9)
                elif "B44" in self._model_name:
                    self._frequency_range = (8e3, 44e9)

        # Initialize the generator
        self.reset()
        # Set up for remote operation
        self._write("SYST:DISP:UPD ON")  # Enable display updates

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

    @property
    def power_range(self) -> tuple:
        """Return the power range (min, max) in dBm."""
        return self._power_range

    def set_frequency(self, channel: int, frequency: float) -> None:
        """
        Set the output frequency.

        Args:
            channel: Channel number (SMA100A has 1 channel)
            frequency: Frequency in Hz
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        if not (self._frequency_range[0] <= frequency <= self._frequency_range[1]):
            raise ValueError(f"Frequency {frequency} outside valid range {self._frequency_range}")

        self._write(f"SOUR:FREQ {frequency}")

    def get_frequency(self, channel: int) -> float:
        """
        Get the current output frequency.

        Args:
            channel: Channel number

        Returns:
            Frequency in Hz
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        response = self._query("SOUR:FREQ?")
        return float(response)

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """
        Set the output amplitude (power level).

        Args:
            channel: Channel number
            amplitude: Amplitude in dBm
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        if not (self._power_range[0] <= amplitude <= self._power_range[1]):
            raise ValueError(f"Amplitude {amplitude} outside valid range {self._power_range}")

        self._write(f"SOUR:POW {amplitude}")

    def get_amplitude(self, channel: int) -> float:
        """
        Get the current output amplitude.

        Args:
            channel: Channel number

        Returns:
            Amplitude in dBm
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        response = self._query("SOUR:POW?")
        return float(response)

    def set_waveform(self, channel: int, waveform: str) -> None:
        """
        Set the output waveform type.

        Note: SMA100A is primarily a CW generator, but supports some modulation modes.

        Args:
            channel: Channel number
            waveform: Waveform type ('CW', 'AM', 'FM', 'PM')
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        valid_waveforms = ["CW", "AM", "FM", "PM"]
        if waveform.upper() not in valid_waveforms:
            raise ValueError(f"Invalid waveform: {waveform}. Valid types: {valid_waveforms}")

        if waveform.upper() == "CW":
            # Disable all modulation
            self._write("SOUR:AM:STAT OFF")
            self._write("SOUR:FM:STAT OFF")
            self._write("SOUR:PM:STAT OFF")
        elif waveform.upper() == "AM":
            self._write("SOUR:AM:STAT ON")
            self._write("SOUR:FM:STAT OFF")
            self._write("SOUR:PM:STAT OFF")
        elif waveform.upper() == "FM":
            self._write("SOUR:AM:STAT OFF")
            self._write("SOUR:FM:STAT ON")
            self._write("SOUR:PM:STAT OFF")
        elif waveform.upper() == "PM":
            self._write("SOUR:AM:STAT OFF")
            self._write("SOUR:FM:STAT OFF")
            self._write("SOUR:PM:STAT ON")

    def get_waveform(self, channel: int) -> str:
        """
        Get the current waveform type.

        Args:
            channel: Channel number

        Returns:
            Waveform type
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        # Check which modulation is active
        am_state = self._query("SOUR:AM:STAT?")
        fm_state = self._query("SOUR:FM:STAT?")
        pm_state = self._query("SOUR:PM:STAT?")

        if am_state.strip() == "1":
            return "AM"
        elif fm_state.strip() == "1":
            return "FM"
        elif pm_state.strip() == "1":
            return "PM"
        else:
            return "CW"

    def set_output_enabled(self, channel: int, enabled: bool) -> None:
        """
        Enable or disable the RF output.

        Args:
            channel: Channel number
            enabled: True to enable output, False to disable
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        state = "ON" if enabled else "OFF"
        self._write(f"OUTP {state}")

    def get_output_enabled(self, channel: int) -> bool:
        """
        Get the current output state.

        Args:
            channel: Channel number

        Returns:
            True if output is enabled, False otherwise
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        response = self._query("OUTP?")
        return response.strip() == "1"

    def set_phase(self, channel: int, phase: float) -> None:
        """
        Set the output phase.

        Args:
            channel: Channel number
            phase: Phase in degrees
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        self._write(f"SOUR:PHAS {phase}")

    def get_phase(self, channel: int) -> float:
        """
        Get the current output phase.

        Args:
            channel: Channel number

        Returns:
            Phase in degrees
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        response = self._query("SOUR:PHAS?")
        return float(response)

    def set_dc_offset(self, channel: int, offset: float) -> None:
        """
        Set DC offset (not applicable for RF generators).

        Args:
            channel: Channel number
            offset: DC offset in volts

        Raises:
            NotImplementedError: DC offset not applicable for RF generators
        """
        raise NotImplementedError("DC offset not applicable for RF signal generators")

    def get_dc_offset(self, channel: int) -> float:
        """
        Get DC offset (not applicable for RF generators).

        Args:
            channel: Channel number

        Returns:
            DC offset in volts

        Raises:
            NotImplementedError: DC offset not applicable for RF generators
        """
        raise NotImplementedError("DC offset not applicable for RF signal generators")

    def set_modulation_frequency(self, channel: int, mod_frequency: float) -> None:
        """
        Set the modulation frequency for AM/FM/PM.

        Args:
            channel: Channel number
            mod_frequency: Modulation frequency in Hz
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        # Set modulation frequency for all modulation types
        self._write(f"SOUR:AM:INT:FREQ {mod_frequency}")
        self._write(f"SOUR:FM:INT:FREQ {mod_frequency}")
        self._write(f"SOUR:PM:INT:FREQ {mod_frequency}")

    def get_modulation_frequency(self, channel: int) -> float:
        """
        Get the current modulation frequency.

        Args:
            channel: Channel number

        Returns:
            Modulation frequency in Hz
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        # Return the internal modulation frequency
        response = self._query("SOUR:AM:INT:FREQ?")
        return float(response)

    def set_modulation_depth(self, channel: int, depth: float) -> None:
        """
        Set the modulation depth.

        Args:
            channel: Channel number
            depth: Modulation depth (0-100% for AM, Hz for FM, degrees for PM)
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        # Get current modulation type and set appropriate depth
        waveform = self.get_waveform(channel)

        if waveform == "AM":
            if not 0 <= depth <= 100:
                raise ValueError("AM modulation depth must be 0-100%")
            self._write(f"SOUR:AM:DEPT {depth}")
        elif waveform == "FM":
            self._write(f"SOUR:FM:DEV {depth}")  # depth in Hz
        elif waveform == "PM":
            self._write(f"SOUR:PM:DEV {depth}")  # depth in degrees
        else:
            raise ValueError("Modulation depth only applicable when modulation is enabled")

    def get_modulation_depth(self, channel: int) -> float:
        """
        Get the current modulation depth.

        Args:
            channel: Channel number

        Returns:
            Modulation depth
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        waveform = self.get_waveform(channel)

        if waveform == "AM":
            response = self._query("SOUR:AM:DEPT?")
        elif waveform == "FM":
            response = self._query("SOUR:FM:DEV?")
        elif waveform == "PM":
            response = self._query("SOUR:PM:DEV?")
        else:
            return 0.0

        return float(response)

    def set_reference_oscillator(self, source: str) -> None:
        """
        Set the reference oscillator source.

        Args:
            source: 'INT' (internal) or 'EXT' (external)
        """
        if source.upper() not in ["INT", "INTERNAL", "EXT", "EXTERNAL"]:
            raise ValueError("Reference source must be 'INT' or 'EXT'")

        if source.upper() in ["INT", "INTERNAL"]:
            self._write("SOUR:ROSC:SOUR INT")
        else:
            self._write("SOUR:ROSC:SOUR EXT")

    def get_reference_oscillator(self) -> str:
        """
        Get the current reference oscillator source.

        Returns:
            Reference source ('INT' or 'EXT')
        """
        response = self._query("SOUR:ROSC:SOUR?")
        return response.strip()

    def set_attenuator_mode(self, mode: str) -> None:
        """
        Set the attenuator mode.

        Args:
            mode: 'AUTO' or 'FIX' (fixed)
        """
        if mode.upper() not in ["AUTO", "FIX", "FIXED"]:
            raise ValueError("Attenuator mode must be 'AUTO' or 'FIX'")

        if mode.upper() == "AUTO":
            self._write("SOUR:POW:ATT:AUTO ON")
        else:
            self._write("SOUR:POW:ATT:AUTO OFF")

    def get_attenuator_mode(self) -> str:
        """
        Get the current attenuator mode.

        Returns:
            Attenuator mode ('AUTO' or 'FIX')
        """
        response = self._query("SOUR:POW:ATT:AUTO?")
        return "AUTO" if response.strip() == "1" else "FIX"

    def trigger(self, channel: int) -> None:
        """
        Send a trigger signal.

        Args:
            channel: Channel number
        """
        if channel != 1:
            raise ValueError("SMA100A has only 1 channel")

        self._write("TRIG:EXEC")

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
                "frequency": self.get_frequency(1),
                "power": self.get_amplitude(1),
                "output_enabled": self.get_output_enabled(1),
                "waveform": self.get_waveform(1),
                "phase": self.get_phase(1),
                "reference_oscillator": self.get_reference_oscillator(),
                "attenuator_mode": self.get_attenuator_mode(),
                "errors": self.get_error_queue()
            }

            # Add modulation info if enabled
            waveform = status["waveform"]
            if waveform != "CW":
                status["modulation_frequency"] = self.get_modulation_frequency(1)
                status["modulation_depth"] = self.get_modulation_depth(1)

        except Exception as e:
            status = {"error": str(e)}

        return status


class MockSMA100A(RohdeSchwarzSMA100A):
    """Mock version of Rohde & Schwarz SMA100A for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 5000, retry_config=None, model: str = "SMA100A"):
        """Initialize mock SMA100A."""
        super().__init__(address, timeout, retry_config)
        self._mock_model = model
        self._mock_states: Dict[str, Any] = {}
        self._init_mock_states()

    def _init_mock_states(self) -> None:
        """Initialize mock internal states."""
        self._mock_states = {
            "frequency": 1e9,           # 1 GHz
            "power": -10.0,             # -10 dBm
            "output_enabled": False,
            "phase": 0.0,               # 0 degrees
            "waveform": "CW",
            "am_enabled": False,
            "fm_enabled": False,
            "pm_enabled": False,
            "modulation_frequency": 1000,  # 1 kHz
            "am_depth": 50.0,           # 50%
            "fm_deviation": 10000,      # 10 kHz
            "pm_deviation": 1.0,        # 1 degree
            "reference_source": "INT",
            "attenuator_auto": True
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

    def _write(self, command: str) -> None:
        """Mock VISA write operation."""
        self._logger.debug(f"Mock VISA write: {command}")

        # Parse common commands and update mock state
        if "SOUR:FREQ" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["frequency"] = value
        elif "SOUR:POW:ATT:AUTO ON" in command:
            self._mock_states["attenuator_auto"] = True
        elif "SOUR:POW:ATT:AUTO OFF" in command:
            self._mock_states["attenuator_auto"] = False
        elif "SOUR:POW" in command and "?" not in command and "ATT" not in command:
            value = float(command.split()[-1])
            self._mock_states["power"] = value
        elif "OUTP ON" in command:
            self._mock_states["output_enabled"] = True
        elif "OUTP OFF" in command:
            self._mock_states["output_enabled"] = False
        elif "SOUR:PHAS" in command and "?" not in command:
            value = float(command.split()[-1])
            self._mock_states["phase"] = value
        elif "SOUR:AM:STAT ON" in command:
            self._mock_states["am_enabled"] = True
            self._mock_states["waveform"] = "AM"
        elif "SOUR:AM:STAT OFF" in command:
            self._mock_states["am_enabled"] = False
        elif "SOUR:FM:STAT ON" in command:
            self._mock_states["fm_enabled"] = True
            self._mock_states["waveform"] = "FM"
        elif "SOUR:FM:STAT OFF" in command:
            self._mock_states["fm_enabled"] = False
        elif "SOUR:PM:STAT ON" in command:
            self._mock_states["pm_enabled"] = True
            self._mock_states["waveform"] = "PM"
        elif "SOUR:PM:STAT OFF" in command:
            self._mock_states["pm_enabled"] = False
        elif "SOUR:ROSC:SOUR" in command and "?" not in command:
            value = command.split()[-1].strip()
            self._mock_states["reference_source"] = value

        # Update waveform type based on enabled modulations
        if not any([self._mock_states["am_enabled"],
                   self._mock_states["fm_enabled"],
                   self._mock_states["pm_enabled"]]):
            self._mock_states["waveform"] = "CW"

    def _query(self, command: str) -> str:
        """Mock VISA query operation."""
        if "SOUR:FREQ?" in command:
            return str(self._mock_states["frequency"])
        elif "SOUR:POW?" in command:
            return str(self._mock_states["power"])
        elif "OUTP?" in command:
            return "1" if self._mock_states["output_enabled"] else "0"
        elif "SOUR:PHAS?" in command:
            return str(self._mock_states["phase"])
        elif "SOUR:AM:STAT?" in command:
            return "1" if self._mock_states["am_enabled"] else "0"
        elif "SOUR:FM:STAT?" in command:
            return "1" if self._mock_states["fm_enabled"] else "0"
        elif "SOUR:PM:STAT?" in command:
            return "1" if self._mock_states["pm_enabled"] else "0"
        elif "SOUR:AM:INT:FREQ?" in command:
            return str(self._mock_states["modulation_frequency"])
        elif "SOUR:AM:DEPT?" in command:
            return str(self._mock_states["am_depth"])
        elif "SOUR:FM:DEV?" in command:
            return str(self._mock_states["fm_deviation"])
        elif "SOUR:PM:DEV?" in command:
            return str(self._mock_states["pm_deviation"])
        elif "SOUR:ROSC:SOUR?" in command:
            return self._mock_states["reference_source"]
        elif "SOUR:POW:ATT:AUTO?" in command:
            return "1" if self._mock_states["attenuator_auto"] else "0"
        return "MOCK_RESPONSE"

    def reset(self) -> None:
        """Mock reset."""
        self._init_mock_states()
        self._logger.debug("Mock SMA100A reset")

    def self_test(self) -> bool:
        """Mock self test."""
        return True

    def get_error_queue(self) -> List[str]:
        """Mock error queue."""
        return []

    def set_offset(self, offset: float, channel: int = 1) -> None:
        """Set DC offset (not applicable for RF generators)."""
        self._logger.warning("DC offset not applicable for RF signal generator")

    def get_offset(self, channel: int = 1) -> float:
        """Get DC offset (not applicable for RF generators)."""
        return 0.0

    def set_output_state(self, enabled: bool, channel: int = 1) -> None:
        """Set output state using FunctionGenerator interface."""
        self.set_output_enabled(channel, enabled)

    def get_output_state(self, channel: int = 1) -> bool:
        """Get output state using FunctionGenerator interface."""
        return self.get_output_enabled(channel)