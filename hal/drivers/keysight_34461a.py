"""Driver for Keysight 34461A Digital Multimeter."""

import time
from typing import Optional

from ..interfaces import CommunicationError, DigitalMultimeter
from ..visa_instrument import VisaInstrument


class Keysight34461A(VisaInstrument, DigitalMultimeter):
    """
    Driver for Keysight 34461A 6½ Digit Multimeter.

    This driver provides a complete interface to the Keysight 34461A DMM
    including all measurement functions and configuration options.
    """

    def __init__(self, address: Optional[str] = None, timeout: int = 10000, retry_config=None):
        """
        Initialize the multimeter driver.

        Args:
            address: VISA address of the instrument
            timeout: Communication timeout in milliseconds (default 10s for measurements)
            retry_config: Retry configuration for communication
        """
        super().__init__(address, timeout, retry_config)
        self._model_name = ""
        self._serial_number = ""

    def connect(self, address: Optional[str] = None) -> None:
        """Connect to the multimeter and initialize."""
        super().connect(address)

        # Parse identification string
        idn = self._identify()
        parts = idn.split(',')
        if len(parts) >= 4:
            self._model_name = parts[1].strip()
            self._serial_number = parts[2].strip()

        # Initialize the instrument
        self.reset()
        # Clear error queue
        self.get_error_queue()
        # Set to high resolution mode
        self._write("SENS:VOLT:DC:NPLC 10")  # 10 power line cycles for best accuracy

    @property
    def model_name(self) -> str:
        """Return the instrument's model name."""
        return self._model_name

    @property
    def serial_number(self) -> str:
        """Return the instrument's serial number."""
        return self._serial_number

    def measure_dc_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform a DC voltage measurement."""
        cmd = "MEAS:VOLT:DC?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")  # Default range
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def measure_ac_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform an AC voltage measurement."""
        cmd = "MEAS:VOLT:AC?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def measure_dc_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform a DC current measurement."""
        cmd = "MEAS:CURR:DC?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def measure_ac_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform an AC current measurement."""
        cmd = "MEAS:CURR:AC?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def measure_resistance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform a resistance measurement."""
        cmd = "MEAS:RES?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def measure_capacitance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Perform a capacitance measurement."""
        cmd = "MEAS:CAP?"

        # Build command with optional parameters
        params = []
        if range is not None:
            params.append(str(range))
            if resolution is not None:
                params.append(str(resolution))
        elif resolution is not None:
            params.append("DEF")
            params.append(str(resolution))

        if params:
            cmd += " " + ",".join(params)

        response = self._query(cmd)
        return float(response)

    def configure_measurement(self, function: str, range: Optional[float] = None, resolution: Optional[float] = None) -> None:
        """Configure the DMM for a specific measurement without triggering."""
        function_map = {
            "VDC": "VOLT:DC",
            "VAC": "VOLT:AC",
            "IDC": "CURR:DC",
            "IAC": "CURR:AC",
            "RES": "RES",
            "CAP": "CAP",
            "FREQ": "FREQ",
            "PER": "PER",
            "DIODE": "DIOD",
            "CONT": "CONT"
        }

        if function not in function_map:
            raise ValueError(f"Invalid function: {function}. Valid options: {list(function_map.keys())}")

        scpi_function = function_map[function]

        # Configure function
        self._write(f"CONF:{scpi_function}")

        # Set range if specified
        if range is not None:
            self._write(f"SENS:{scpi_function}:RANG {range}")
        else:
            self._write(f"SENS:{scpi_function}:RANG:AUTO ON")

        # Set resolution if specified
        if resolution is not None:
            self._write(f"SENS:{scpi_function}:RES {resolution}")

    def trigger_measurement(self) -> None:
        """Trigger a measurement using the current configuration."""
        self._write("INIT")

    def read_measurement(self) -> float:
        """Read the result of a previously triggered measurement."""
        response = self._query("FETC?")
        return float(response)

    def set_nplc(self, nplc: float) -> None:
        """
        Set the number of power line cycles for integration.

        Args:
            nplc: Number of power line cycles (0.02 to 100 for 34461A)
                 Higher values = better resolution, slower measurement
        """
        # Get current function to apply NPLC to correct measurement type
        function = self._query("CONF?").split()[0].replace('"', '')

        if "VOLT:DC" in function or "CURR:DC" in function or "RES" in function:
            self._write(f"SENS:{function}:NPLC {nplc}")
        else:
            self._logger.warning(f"NPLC not applicable to function: {function}")

    def get_nplc(self) -> float:
        """Get the current NPLC setting."""
        function = self._query("CONF?").split()[0].replace('"', '')

        if "VOLT:DC" in function or "CURR:DC" in function or "RES" in function:
            response = self._query(f"SENS:{function}:NPLC?")
            return float(response)
        else:
            return 1.0  # Default

    def set_auto_zero(self, enabled: bool) -> None:
        """
        Enable or disable auto-zero for improved accuracy.

        Args:
            enabled: True to enable auto-zero, False to disable
        """
        state = "ON" if enabled else "OFF"
        self._write(f"SENS:ZERO:AUTO {state}")

    def get_auto_zero(self) -> bool:
        """Get the auto-zero state."""
        response = self._query("SENS:ZERO:AUTO?")
        return response.strip() == "1"

    def set_input_impedance(self, high_impedance: bool) -> None:
        """
        Set input impedance for voltage measurements.

        Args:
            high_impedance: True for >10GOhm (default), False for 10MOhm
        """
        impedance = "AUTO" if high_impedance else "10M"
        self._write(f"SENS:VOLT:IMP {impedance}")

    def get_input_impedance(self) -> str:
        """Get the current input impedance setting."""
        response = self._query("SENS:VOLT:IMP?")
        return response.strip()

    def measure_temperature(self, sensor_type: str = "RTD", range: Optional[float] = None) -> float:
        """
        Measure temperature using connected sensor.

        Args:
            sensor_type: Sensor type ("RTD", "THER", "FRTD")
            range: Temperature range (optional)

        Returns:
            Temperature in Celsius
        """
        if sensor_type not in ["RTD", "THER", "FRTD"]:
            raise ValueError("Invalid sensor type. Use 'RTD', 'THER', or 'FRTD'")

        cmd = f"MEAS:TEMP? {sensor_type}"
        if range is not None:
            cmd += f",{range}"

        response = self._query(cmd)
        return float(response)

    def get_status(self) -> dict:
        """
        Get comprehensive status information.

        Returns:
            Dictionary containing current configuration and settings
        """
        status = {
            "model": self.model_name,
            "serial": self.serial_number,
            "connected": self.is_connected,
        }

        try:
            # Get current configuration
            config = self._query("CONF?")
            status["configuration"] = config.strip()

            # Get current function
            function = config.split()[0].replace('"', '')
            status["function"] = function

            # Get function-specific settings
            if "VOLT:DC" in function or "CURR:DC" in function or "RES" in function:
                status["nplc"] = self.get_nplc()
                status["auto_zero"] = self.get_auto_zero()

            if "VOLT" in function:
                status["input_impedance"] = self.get_input_impedance()

            # Check for errors
            errors = self.get_error_queue()
            status["errors"] = errors

        except CommunicationError as e:
            status["error"] = str(e)

        return status


class Mock34461A(Keysight34461A):
    """Mock version of Keysight 34461A for testing without hardware."""

    def __init__(self, address: Optional[str] = None, timeout: int = 10000, retry_config=None):
        """Initialize mock multimeter."""
        super().__init__(address, timeout, retry_config)
        self._mock_function = "VOLT:DC"
        self._mock_range = 10.0
        self._mock_resolution = 0.0001
        self._mock_nplc = 10.0

    @property
    def is_connected(self) -> bool:
        """Return mock connection status."""
        return getattr(self, '_connected', False)

    def connect(self, address: Optional[str] = None) -> None:
        """Mock connection."""
        if address:
            self.address = address
        if not self.address:
            self.address = "MOCK::34461A"

        self._connected = True
        self._model_name = "34461A"
        self._serial_number = "MOCK123456"
        self._logger.info(f"Mock 34461A connected at {self.address}")

    def measure_dc_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock DC voltage measurement."""
        import random
        # Simulate a more realistic voltage measurement that could be influenced by connected sources
        # For testing, we'll simulate measurement of whatever voltage is "present" (around 5V by default)
        base_voltage = getattr(self, '_simulated_voltage', 5.0)
        return base_voltage + random.uniform(-0.01, 0.01)

    def set_simulated_voltage(self, voltage: float) -> None:
        """Set the simulated voltage for testing (not part of real DMM interface)."""
        self._simulated_voltage = voltage

    def measure_ac_voltage(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock AC voltage measurement."""
        import random
        return 1.414 + random.uniform(-0.001, 0.001)  # ~1V RMS

    def measure_dc_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock DC current measurement."""
        import random
        return 0.001 + random.uniform(-0.00001, 0.00001)  # ~1mA

    def measure_ac_current(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock AC current measurement."""
        import random
        return 0.0005 + random.uniform(-0.00001, 0.00001)  # ~0.5mA

    def measure_resistance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock resistance measurement."""
        import random
        return 1000.0 + random.uniform(-1.0, 1.0)  # ~1kOhm

    def measure_capacitance(self, range: Optional[float] = None, resolution: Optional[float] = None) -> float:
        """Mock capacitance measurement."""
        import random
        return 1e-6 + random.uniform(-1e-9, 1e-9)  # ~1µF

    def configure_measurement(self, function: str, range: Optional[float] = None, resolution: Optional[float] = None) -> None:
        """Mock configure measurement."""
        self._mock_function = function
        if range is not None:
            self._mock_range = range
        if resolution is not None:
            self._mock_resolution = resolution
        self._logger.debug(f"Mock configured for {function}")

    def trigger_measurement(self) -> None:
        """Mock trigger measurement."""
        time.sleep(0.1)  # Simulate measurement time

    def read_measurement(self) -> float:
        """Mock read measurement."""
        # Return appropriate mock value based on configured function
        if "VDC" in self._mock_function:
            return self.measure_dc_voltage()
        elif "VAC" in self._mock_function:
            return self.measure_ac_voltage()
        elif "IDC" in self._mock_function:
            return self.measure_dc_current()
        elif "IAC" in self._mock_function:
            return self.measure_ac_current()
        elif "RES" in self._mock_function:
            return self.measure_resistance()
        elif "CAP" in self._mock_function:
            return self.measure_capacitance()
        else:
            return 0.0

    def reset(self) -> None:
        """Mock reset - reset to default state."""
        self._mock_function = "VDC"
        self._mock_range = 10.0
        self._mock_resolution = 0.0001
        self._mock_nplc = 10.0
        self._logger.debug("Mock DMM reset")

    def self_test(self) -> bool:
        """Mock self test - always passes."""
        return True

    def get_error_queue(self) -> list:
        """Mock error queue - no errors."""
        return []
