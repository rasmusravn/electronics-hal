"""
Integration tests for power supply voltage regulation.

These tests verify that power supplies can accurately set and maintain
voltage levels under various conditions.
"""


import pytest

from hal.interfaces import DigitalMultimeter, PowerSupply


class TestVoltageRegulation:
    """Test voltage regulation capabilities of power supplies."""

    @pytest.mark.integration
    @pytest.mark.power_management
    def test_basic_voltage_setting(
        self,
        mock_power_supply: PowerSupply,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test basic voltage setting and measurement."""
        # Test setup
        target_voltage = 5.0
        tolerance = 0.05  # ±50mV

        # Configure power supply
        mock_power_supply.set_voltage(target_voltage, channel=1)
        mock_power_supply.set_current_limit(1.0, channel=1)
        mock_power_supply.set_output_state(True, channel=1)

        # Measure actual voltage
        measured_voltage = mock_multimeter.measure_dc_voltage()

        # Log measurement
        test_logger.log_measurement(
            name="output_voltage",
            value=measured_voltage,
            unit="V",
            limits={"min": target_voltage - tolerance, "max": target_voltage + tolerance},
            target_voltage=target_voltage,
            tolerance=tolerance
        )

        # Verify voltage is within tolerance
        assert abs(measured_voltage - target_voltage) <= tolerance, \
            f"Voltage {measured_voltage}V outside tolerance ±{tolerance}V of {target_voltage}V"

    @pytest.mark.integration
    @pytest.mark.power_management
    @pytest.mark.parametrize(
        "voltage,current_limit,expected_min,expected_max",
        [
            (3.3, 0.5, 3.25, 3.35),   # 3.3V rail test
            (5.0, 1.0, 4.95, 5.05),   # 5V rail test
            (12.0, 2.0, 11.88, 12.12), # 12V rail test
            (1.8, 0.3, 1.782, 1.818), # 1.8V rail test
        ],
    )
    def test_multiple_voltage_levels(
        self,
        voltage: float,
        current_limit: float,
        expected_min: float,
        expected_max: float,
        mock_power_supply: PowerSupply,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test voltage regulation at multiple standard voltage levels."""
        # Configure power supply
        mock_power_supply.configure_channel(
            channel=1,
            voltage=voltage,
            current_limit=current_limit,
            output_enabled=True
        )

        # Allow settling time
        import time
        time.sleep(0.1)

        # Measure output voltage
        measured_voltage = mock_multimeter.measure_dc_voltage()

        # Log measurement with test parameters
        test_logger.log_measurement(
            name=f"voltage_{voltage}V",
            value=measured_voltage,
            unit="V",
            limits={"min": expected_min, "max": expected_max},
            target_voltage=voltage,
            current_limit=current_limit
        )

        # Verify voltage is within specification
        assert expected_min <= measured_voltage <= expected_max, \
            f"Voltage {measured_voltage}V outside spec [{expected_min}, {expected_max}]V"

    @pytest.mark.integration
    @pytest.mark.power_management
    def test_load_regulation(
        self,
        mock_power_supply: PowerSupply,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test voltage regulation under different load conditions."""
        target_voltage = 5.0
        voltage_tolerance = 0.02  # ±20mV load regulation

        # Set up power supply
        mock_power_supply.configure_channel(
            channel=1,
            voltage=target_voltage,
            current_limit=2.0,
            output_enabled=True
        )

        # Test different load conditions (simulated via different current limits)
        load_conditions = [
            ("no_load", 0.001),
            ("light_load", 0.1),
            ("medium_load", 0.5),
            ("heavy_load", 1.0),
        ]

        voltages = {}

        for load_name, current in load_conditions:
            # Simulate load by setting current limit (mock will simulate current draw)
            mock_power_supply.set_current_limit(current, channel=1)

            # Allow settling
            import time
            time.sleep(0.05)

            # Measure voltage under this load
            measured_voltage = mock_multimeter.measure_dc_voltage()
            voltages[load_name] = measured_voltage

            # Log measurement
            test_logger.log_measurement(
                name=f"voltage_under_{load_name}",
                value=measured_voltage,
                unit="V",
                limits={"min": target_voltage - voltage_tolerance, "max": target_voltage + voltage_tolerance},
                load_current=current,
                load_condition=load_name
            )

        # Calculate load regulation (max voltage variation)
        voltage_values = list(voltages.values())
        load_regulation = max(voltage_values) - min(voltage_values)

        test_logger.log_measurement(
            name="load_regulation",
            value=load_regulation,
            unit="V",
            limits={"max": voltage_tolerance * 2},  # Total allowed variation
            voltage_range=f"{min(voltage_values):.4f}V to {max(voltage_values):.4f}V"
        )

        # Verify load regulation meets specification
        assert load_regulation <= voltage_tolerance * 2, \
            f"Load regulation {load_regulation:.4f}V exceeds {voltage_tolerance * 2}V"

    @pytest.mark.integration
    @pytest.mark.power_management
    def test_multi_channel_independence(
        self,
        mock_power_supply: PowerSupply,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test that multiple channels operate independently."""
        # Skip if single-channel power supply
        if mock_power_supply.num_channels < 2:
            pytest.skip("Test requires multi-channel power supply")

        # Configure different voltages on each channel
        ch1_voltage = 3.3
        ch2_voltage = 5.0

        mock_power_supply.configure_channel(1, ch1_voltage, 1.0, True)
        mock_power_supply.configure_channel(2, ch2_voltage, 1.0, True)

        # Allow settling
        import time
        time.sleep(0.1)

        # Measure both channels
        # Note: In real hardware, you'd need to switch DMM inputs or use multiple DMMs
        # For mock testing, we'll simulate this
        measured_ch1 = mock_power_supply.measure_voltage(1)  # Use PS measurement capability
        measured_ch2 = mock_power_supply.measure_voltage(2)

        # Log measurements
        test_logger.log_measurement(
            name="channel_1_voltage",
            value=measured_ch1,
            unit="V",
            limits={"min": ch1_voltage - 0.05, "max": ch1_voltage + 0.05},
            channel=1,
            target=ch1_voltage
        )

        test_logger.log_measurement(
            name="channel_2_voltage",
            value=measured_ch2,
            unit="V",
            limits={"min": ch2_voltage - 0.05, "max": ch2_voltage + 0.05},
            channel=2,
            target=ch2_voltage
        )

        # Verify both channels are correct
        assert abs(measured_ch1 - ch1_voltage) <= 0.05
        assert abs(measured_ch2 - ch2_voltage) <= 0.05

        # Test channel independence: change channel 1, verify channel 2 unaffected
        new_ch1_voltage = 2.5
        mock_power_supply.set_voltage(new_ch1_voltage, 1)

        time.sleep(0.05)

        measured_ch1_new = mock_power_supply.measure_voltage(1)
        measured_ch2_after = mock_power_supply.measure_voltage(2)

        test_logger.log_measurement(
            name="channel_1_after_change",
            value=measured_ch1_new,
            unit="V",
            limits={"min": new_ch1_voltage - 0.05, "max": new_ch1_voltage + 0.05},
            channel=1,
            target=new_ch1_voltage
        )

        test_logger.log_measurement(
            name="channel_2_independence_check",
            value=measured_ch2_after,
            unit="V",
            limits={"min": ch2_voltage - 0.05, "max": ch2_voltage + 0.05},
            channel=2,
            target=ch2_voltage,
            test_type="independence"
        )

        # Verify channel 1 changed and channel 2 remained stable
        assert abs(measured_ch1_new - new_ch1_voltage) <= 0.05
        assert abs(measured_ch2_after - ch2_voltage) <= 0.05
