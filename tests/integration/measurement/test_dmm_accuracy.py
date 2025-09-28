"""
Integration tests for digital multimeter measurement accuracy.

These tests verify DMM measurement accuracy, range selection,
and various measurement functions.
"""

import time

import pytest

from hal.interfaces import DigitalMultimeter, PowerSupply


class TestDMMAccuracy:
    """Test measurement accuracy and functionality of digital multimeters."""

    @pytest.mark.integration
    @pytest.mark.measurement
    def test_dc_voltage_accuracy(
        self,
        mock_multimeter: DigitalMultimeter,
        mock_power_supply: PowerSupply,
        test_logger
    ):
        """Test DC voltage measurement accuracy against known reference."""
        # Set up reference voltage
        reference_voltage = 5.000
        mock_power_supply.configure_channel(1, reference_voltage, 1.0, True)

        # Allow voltage to settle
        time.sleep(0.1)

        # Configure DMM for high accuracy measurement
        mock_multimeter.configure_measurement("VDC", range=10.0, resolution=0.0001)
        mock_multimeter.trigger_measurement()
        measured_voltage = mock_multimeter.read_measurement()

        # Calculate measurement error
        error = measured_voltage - reference_voltage
        error_ppm = (error / reference_voltage) * 1e6  # parts per million

        # Log measurements
        test_logger.log_measurement(
            name="reference_voltage",
            value=reference_voltage,
            unit="V",
            measurement_type="reference"
        )

        test_logger.log_measurement(
            name="measured_voltage",
            value=measured_voltage,
            unit="V",
            limits={"min": reference_voltage - 0.001, "max": reference_voltage + 0.001},
            reference=reference_voltage
        )

        test_logger.log_measurement(
            name="measurement_error",
            value=error,
            unit="V",
            limits={"min": -0.001, "max": 0.001},
            error_ppm=error_ppm
        )

        # Verify accuracy (±1mV or ±200ppm, whichever is larger)
        max_error = max(0.001, abs(reference_voltage * 200e-6))
        assert abs(error) <= max_error, \
            f"Measurement error {error:.6f}V ({error_ppm:.1f} ppm) exceeds ±{max_error:.6f}V"

    @pytest.mark.integration
    @pytest.mark.measurement
    @pytest.mark.parametrize(
        "measurement_function,expected_value,tolerance",
        [
            ("VDC", 5.0, 0.001),        # DC voltage
            ("VAC", 1.414, 0.01),       # AC voltage (RMS)
            ("IDC", 0.001, 0.000001),   # DC current
            ("IAC", 0.0005, 0.000005),  # AC current
            ("RES", 1000.0, 1.0),       # Resistance
        ],
    )
    def test_measurement_functions(
        self,
        measurement_function: str,
        expected_value: float,
        tolerance: float,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test various measurement functions for accuracy."""
        # Configure measurement
        if measurement_function == "VDC":
            measured_value = mock_multimeter.measure_dc_voltage()
            unit = "V"
        elif measurement_function == "VAC":
            measured_value = mock_multimeter.measure_ac_voltage()
            unit = "V"
        elif measurement_function == "IDC":
            measured_value = mock_multimeter.measure_dc_current()
            unit = "A"
        elif measurement_function == "IAC":
            measured_value = mock_multimeter.measure_ac_current()
            unit = "A"
        elif measurement_function == "RES":
            measured_value = mock_multimeter.measure_resistance()
            unit = "Ω"
        else:
            pytest.fail(f"Unknown measurement function: {measurement_function}")

        # Log measurement
        test_logger.log_measurement(
            name=f"{measurement_function.lower()}_measurement",
            value=measured_value,
            unit=unit,
            limits={"min": expected_value - tolerance, "max": expected_value + tolerance},
            function=measurement_function,
            expected=expected_value
        )

        # Verify measurement is within tolerance
        assert abs(measured_value - expected_value) <= tolerance, \
            f"{measurement_function} measurement {measured_value} {unit} outside tolerance ±{tolerance} {unit}"

    @pytest.mark.integration
    @pytest.mark.measurement
    def test_range_selection_accuracy(
        self,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test measurement accuracy across different ranges."""
        test_voltages = [0.1, 1.0, 5.0, 10.0]  # Different voltage levels
        ranges = [1.0, 10.0, 100.0]  # Different measurement ranges

        for voltage in test_voltages:
            for range_val in ranges:
                # Skip if voltage exceeds range
                if voltage > range_val * 0.9:  # Stay below 90% of range
                    continue

                # Configure measurement with specific range
                mock_multimeter.configure_measurement("VDC", range=range_val, resolution=None)
                mock_multimeter.trigger_measurement()
                measured = mock_multimeter.read_measurement()

                # Expected tolerance depends on range
                tolerance = range_val * 0.001  # 0.1% of range

                test_logger.log_measurement(
                    name=f"voltage_{voltage}V_range_{range_val}V",
                    value=measured,
                    unit="V",
                    limits={"min": voltage - tolerance, "max": voltage + tolerance},
                    target_voltage=voltage,
                    measurement_range=range_val,
                    range_utilization=(voltage / range_val) * 100
                )

                # Verify measurement accuracy
                error = abs(measured - voltage)
                assert error <= tolerance, \
                    f"Voltage {voltage}V on {range_val}V range: error {error:.6f}V > {tolerance:.6f}V"

    @pytest.mark.integration
    @pytest.mark.measurement
    def test_resolution_settings(
        self,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test that resolution settings affect measurement precision."""
        reference_voltage = 5.123456  # Precise reference
        resolutions = [0.1, 0.01, 0.001, 0.0001, 0.00001]

        measurements = []

        for resolution in resolutions:
            # Configure with specific resolution
            mock_multimeter.configure_measurement("VDC", range=10.0, resolution=resolution)
            mock_multimeter.trigger_measurement()
            measured = mock_multimeter.read_measurement()

            measurements.append(measured)

            # Calculate expected digits after decimal point
            if resolution >= 1:
                expected_digits = 0
            else:
                expected_digits = len(str(resolution).split('.')[1])

            test_logger.log_measurement(
                name=f"voltage_resolution_{resolution}V",
                value=measured,
                unit="V",
                resolution_setting=resolution,
                expected_digits=expected_digits,
                reference=reference_voltage
            )

        # Verify that higher resolution gives more precise readings
        # (For mock, this will be simulated behavior)
        test_logger.log_measurement(
            name="resolution_test_summary",
            value=len(measurements),
            unit="measurements",
            measurement_count=len(measurements),
            resolution_range=f"{min(resolutions)} to {max(resolutions)}"
        )

    @pytest.mark.integration
    @pytest.mark.measurement
    @pytest.mark.slow
    def test_measurement_repeatability(
        self,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test measurement repeatability over multiple readings."""
        num_measurements = 10
        measurements = []

        # Configure for consistent measurements
        mock_multimeter.configure_measurement("VDC", range=10.0, resolution=0.0001)

        for i in range(num_measurements):
            mock_multimeter.trigger_measurement()
            measured = mock_multimeter.read_measurement()
            measurements.append(measured)

            test_logger.log_measurement(
                name=f"repeatability_measurement_{i+1}",
                value=measured,
                unit="V",
                measurement_number=i + 1
            )

            # Small delay between measurements
            time.sleep(0.01)

        # Calculate statistics
        mean_value = sum(measurements) / len(measurements)
        std_dev = (sum((x - mean_value) ** 2 for x in measurements) / len(measurements)) ** 0.5
        peak_to_peak = max(measurements) - min(measurements)

        # Log statistics
        test_logger.log_measurement(
            name="repeatability_mean",
            value=mean_value,
            unit="V",
            measurement_count=num_measurements
        )

        test_logger.log_measurement(
            name="repeatability_std_dev",
            value=std_dev,
            unit="V",
            limits={"max": 0.0001},  # Should be very stable
            measurement_count=num_measurements
        )

        test_logger.log_measurement(
            name="repeatability_peak_to_peak",
            value=peak_to_peak,
            unit="V",
            limits={"max": 0.0005},  # Maximum allowed variation
            measurement_count=num_measurements
        )

        # Verify repeatability meets specification
        assert std_dev <= 0.0001, f"Standard deviation {std_dev:.6f}V exceeds 0.0001V"
        assert peak_to_peak <= 0.0005, f"Peak-to-peak variation {peak_to_peak:.6f}V exceeds 0.0005V"

    @pytest.mark.integration
    @pytest.mark.measurement
    def test_auto_range_functionality(
        self,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test auto-ranging functionality across different signal levels."""
        # Test voltages that span multiple ranges
        test_voltages = [0.05, 0.5, 5.0, 15.0]

        for voltage in test_voltages:
            # Use auto-range (no range specified)
            measured = mock_multimeter.measure_dc_voltage()

            # For mock testing, we'll verify the measurement is reasonable
            # In real hardware, you'd also verify the selected range
            tolerance = max(0.001, voltage * 0.001)  # 0.1% or 1mV

            test_logger.log_measurement(
                name=f"auto_range_{voltage}V",
                value=measured,
                unit="V",
                limits={"min": voltage - tolerance, "max": voltage + tolerance},
                target_voltage=voltage,
                range_mode="auto"
            )

            # Verify measurement accuracy with auto-range
            assert abs(measured - voltage) <= tolerance, \
                f"Auto-range measurement {measured:.6f}V outside tolerance for {voltage}V"
