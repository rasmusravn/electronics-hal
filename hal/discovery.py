"""Instrument discovery and auto-detection system."""

import re
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass

import pyvisa

from .interfaces import InstrumentInterface, PowerSupply, DigitalMultimeter, FunctionGenerator, Oscilloscope, SignalAnalyzer
from .drivers.keysight_e36100_series import KeysightE36100Series
from .drivers.keysight_34461a import Keysight34461A
from .drivers.keysight_33500_series import Keysight33500Series
from .drivers.keysight_dsox1000_series import KeysightDSOX1000Series
from .drivers.rohde_schwarz_fswp import RohdeSchwarzFSWP
from .drivers.rohde_schwarz_fsv import RohdeSchwarzFSV
from .drivers.rohde_schwarz_sma100a import RohdeSchwarzSMA100A
from .logging_config import get_logger


@dataclass
class InstrumentInfo:
    """Information about a discovered instrument."""

    address: str
    manufacturer: str
    model: str
    serial_number: str
    firmware_version: str
    instrument_type: str
    driver_class: Optional[Type[InstrumentInterface]] = None
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []


class InstrumentRegistry:
    """Registry of known instrument drivers and their identification patterns."""

    def __init__(self):
        """Initialize the instrument registry."""
        self.logger = get_logger(__name__)
        self._drivers: Dict[str, Dict[str, Any]] = {}
        self._register_builtin_drivers()

    def _register_builtin_drivers(self) -> None:
        """Register built-in instrument drivers."""

        # Keysight E36100 Series Power Supplies
        self.register_driver(
            manufacturer_pattern=r"Keysight Technologies|Agilent Technologies",
            model_pattern=r"E36(10[2-6]A)",
            driver_class=KeysightE36100Series,
            instrument_type="power_supply",
            capabilities=["voltage_control", "current_limit", "multi_channel"]
        )

        # Keysight 34461A Digital Multimeter
        self.register_driver(
            manufacturer_pattern=r"Keysight Technologies|Agilent Technologies",
            model_pattern=r"34461A",
            driver_class=Keysight34461A,
            instrument_type="digital_multimeter",
            capabilities=["dc_voltage", "ac_voltage", "dc_current", "ac_current", "resistance", "capacitance"]
        )

        # Keysight 33500 Series Function Generators
        self.register_driver(
            manufacturer_pattern=r"Keysight Technologies|Agilent Technologies",
            model_pattern=r"335(0[0-9]|1[0-9]|2[0-9])B?",
            driver_class=Keysight33500Series,
            instrument_type="function_generator",
            capabilities=["waveform_generation", "arbitrary_waveforms", "multi_channel"]
        )

        # Keysight DSOX1000 Series Oscilloscopes
        self.register_driver(
            manufacturer_pattern=r"Keysight Technologies|Agilent Technologies",
            model_pattern=r"DSOX1[0-9][0-9][0-9]G?",
            driver_class=KeysightDSOX1000Series,
            instrument_type="oscilloscope",
            capabilities=["waveform_capture", "measurements", "triggering", "multi_channel"]
        )

        # Rohde & Schwarz FSWP Signal Analyzers
        self.register_driver(
            manufacturer_pattern=r"Rohde&Schwarz|ROHDE&SCHWARZ",
            model_pattern=r"FSWP[0-9]+",
            driver_class=RohdeSchwarzFSWP,
            instrument_type="signal_analyzer",
            capabilities=["spectrum_analysis", "signal_analysis", "measurements", "markers", "wide_bandwidth"]
        )

        # Rohde & Schwarz FSV Spectrum Analyzers
        self.register_driver(
            manufacturer_pattern=r"Rohde&Schwarz|ROHDE&SCHWARZ",
            model_pattern=r"FSV[0-9]+",
            driver_class=RohdeSchwarzFSV,
            instrument_type="signal_analyzer",
            capabilities=["spectrum_analysis", "measurements", "markers", "trace_analysis"]
        )

        # Rohde & Schwarz SMA100A Signal Generators
        self.register_driver(
            manufacturer_pattern=r"Rohde&Schwarz|ROHDE&SCHWARZ",
            model_pattern=r"SMA100A",
            driver_class=RohdeSchwarzSMA100A,
            instrument_type="signal_generator",
            capabilities=["rf_generation", "modulation", "high_purity", "cw_generation"]
        )

    def register_driver(
        self,
        manufacturer_pattern: str,
        model_pattern: str,
        driver_class: Type[InstrumentInterface],
        instrument_type: str,
        capabilities: List[str]
    ) -> None:
        """
        Register a new instrument driver.

        Args:
            manufacturer_pattern: Regex pattern to match manufacturer name
            model_pattern: Regex pattern to match model name
            driver_class: Driver class for this instrument
            instrument_type: Type of instrument (e.g., "power_supply", "multimeter")
            capabilities: List of capabilities this instrument supports
        """
        key = f"{manufacturer_pattern}::{model_pattern}"
        self._drivers[key] = {
            "manufacturer_pattern": re.compile(manufacturer_pattern, re.IGNORECASE),
            "model_pattern": re.compile(model_pattern, re.IGNORECASE),
            "driver_class": driver_class,
            "instrument_type": instrument_type,
            "capabilities": capabilities
        }
        self.logger.debug(f"Registered driver for {manufacturer_pattern} {model_pattern}")

    def find_driver(self, manufacturer: str, model: str) -> Optional[Dict[str, Any]]:
        """
        Find a driver for the given manufacturer and model.

        Args:
            manufacturer: Instrument manufacturer
            model: Instrument model

        Returns:
            Driver information if found, None otherwise
        """
        for driver_info in self._drivers.values():
            if (driver_info["manufacturer_pattern"].search(manufacturer) and
                driver_info["model_pattern"].search(model)):
                return driver_info
        return None


class InstrumentDiscovery:
    """Discovers and identifies connected instruments."""

    def __init__(self, registry: Optional[InstrumentRegistry] = None):
        """
        Initialize instrument discovery.

        Args:
            registry: Instrument registry (creates default if None)
        """
        self.registry = registry or InstrumentRegistry()
        self.logger = get_logger(__name__)

    def discover_instruments(self, include_mock: bool = False) -> List[InstrumentInfo]:
        """
        Discover all connected instruments.

        Args:
            include_mock: Whether to include mock instruments in discovery

        Returns:
            List of discovered instruments
        """
        instruments = []

        try:
            rm = pyvisa.ResourceManager()
            resources = rm.list_resources()

            self.logger.info(f"Found {len(resources)} VISA resources")

            for address in resources:
                try:
                    # Skip mock instruments unless explicitly requested
                    if not include_mock and "MOCK" in address.upper():
                        continue

                    instrument_info = self._identify_instrument(rm, address)
                    if instrument_info:
                        instruments.append(instrument_info)
                        self.logger.info(f"Identified: {instrument_info.manufacturer} {instrument_info.model} at {address}")
                    else:
                        self.logger.warning(f"Could not identify instrument at {address}")

                except Exception as e:
                    self.logger.warning(f"Error probing instrument at {address}: {e}")

            rm.close()

        except Exception as e:
            self.logger.error(f"Error during instrument discovery: {e}")

        return instruments

    def _identify_instrument(self, rm: pyvisa.ResourceManager, address: str) -> Optional[InstrumentInfo]:
        """
        Identify a single instrument.

        Args:
            rm: VISA resource manager
            address: VISA address of the instrument

        Returns:
            InstrumentInfo if successful, None otherwise
        """
        try:
            # Open connection
            instrument = rm.open_resource(address)
            instrument.timeout = 5000  # 5 second timeout for identification

            # Query instrument identification
            idn_response = instrument.query("*IDN?").strip()
            instrument.close()

            # Parse IDN response (format: Manufacturer,Model,SerialNumber,FirmwareVersion)
            parts = [part.strip() for part in idn_response.split(',')]
            if len(parts) < 4:
                self.logger.warning(f"Invalid IDN response from {address}: {idn_response}")
                return None

            manufacturer = parts[0]
            model = parts[1]
            serial_number = parts[2]
            firmware_version = parts[3]

            # Find matching driver
            driver_info = self.registry.find_driver(manufacturer, model)

            info = InstrumentInfo(
                address=address,
                manufacturer=manufacturer,
                model=model,
                serial_number=serial_number,
                firmware_version=firmware_version,
                instrument_type=driver_info["instrument_type"] if driver_info else "unknown",
                driver_class=driver_info["driver_class"] if driver_info else None,
                capabilities=driver_info["capabilities"][:] if driver_info else []
            )

            return info

        except Exception as e:
            self.logger.debug(f"Failed to identify instrument at {address}: {e}")
            return None

    def find_instruments_by_type(self, instrument_type: str, include_mock: bool = False) -> List[InstrumentInfo]:
        """
        Find instruments of a specific type.

        Args:
            instrument_type: Type of instrument to find (e.g., "power_supply")
            include_mock: Whether to include mock instruments

        Returns:
            List of matching instruments
        """
        all_instruments = self.discover_instruments(include_mock=include_mock)
        return [inst for inst in all_instruments if inst.instrument_type == instrument_type]

    def find_instruments_by_capability(self, capability: str, include_mock: bool = False) -> List[InstrumentInfo]:
        """
        Find instruments with a specific capability.

        Args:
            capability: Capability to search for (e.g., "voltage_control")
            include_mock: Whether to include mock instruments

        Returns:
            List of matching instruments
        """
        all_instruments = self.discover_instruments(include_mock=include_mock)
        return [inst for inst in all_instruments if capability in inst.capabilities]

    def create_instrument(self, instrument_info: InstrumentInfo) -> Optional[InstrumentInterface]:
        """
        Create an instrument instance from discovery information.

        Args:
            instrument_info: Information about the instrument

        Returns:
            Instrument instance if driver available, None otherwise
        """
        if instrument_info.driver_class is None:
            self.logger.warning(f"No driver available for {instrument_info.manufacturer} {instrument_info.model}")
            return None

        try:
            # Create instrument instance
            instrument = instrument_info.driver_class()
            instrument.connect(instrument_info.address)

            self.logger.info(f"Created {instrument_info.driver_class.__name__} instance for {instrument_info.address}")
            return instrument

        except Exception as e:
            self.logger.error(f"Failed to create instrument instance: {e}")
            return None


# Global discovery instance
_global_discovery = InstrumentDiscovery()


def get_discovery() -> InstrumentDiscovery:
    """Get the global instrument discovery instance."""
    return _global_discovery


def discover_instruments(include_mock: bool = False) -> List[InstrumentInfo]:
    """
    Convenience function to discover all instruments.

    Args:
        include_mock: Whether to include mock instruments

    Returns:
        List of discovered instruments
    """
    return get_discovery().discover_instruments(include_mock=include_mock)


def find_power_supplies(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all power supply instruments."""
    return get_discovery().find_instruments_by_type("power_supply", include_mock=include_mock)


def find_multimeters(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all digital multimeter instruments."""
    return get_discovery().find_instruments_by_type("digital_multimeter", include_mock=include_mock)


def find_function_generators(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all function generator instruments."""
    return get_discovery().find_instruments_by_type("function_generator", include_mock=include_mock)


def find_oscilloscopes(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all oscilloscope instruments."""
    return get_discovery().find_instruments_by_type("oscilloscope", include_mock=include_mock)


def find_signal_analyzers(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all signal and spectrum analyzer instruments."""
    return get_discovery().find_instruments_by_type("signal_analyzer", include_mock=include_mock)


def find_signal_generators(include_mock: bool = False) -> List[InstrumentInfo]:
    """Find all RF signal generator instruments."""
    return get_discovery().find_instruments_by_type("signal_generator", include_mock=include_mock)