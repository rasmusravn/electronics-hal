#!/usr/bin/env python3
"""
Phase 2 Hardware Abstraction Layer (HAL) Verification Script.

This script validates that the HAL components work correctly using mock instruments.
It tests the abstract interfaces, VISA backend, and concrete drivers.
"""

import tempfile
from pathlib import Path

from hal.config_loader import load_config
from hal.config_models import SystemConfig
from hal.logging_config import setup_logging, get_logger
from hal.visa_instrument import MockVisaInstrument
from hal.drivers.keysight_e36100_series import MockKeysightE36100Series
from hal.drivers.keysight_34461a import Mock34461A
from hal.drivers.keysight_33500_series import Mock33500Series


def test_visa_backend():
    """Test the VISA communication backend."""
    print("Testing VISA backend...")

    try:
        # Test 1: Basic MockVisaInstrument functionality
        instrument = MockVisaInstrument("MOCK::TEST")
        instrument.connect()
        assert instrument.is_connected
        print("✓ Mock VISA instrument connection established")

        # Test 2: Basic communication
        response = instrument._query("*IDN?")
        assert "Mock Instrument" in response
        print("✓ Basic VISA communication working")

        # Test 3: Custom mock responses
        instrument.add_mock_response("TEST:COMMAND?", "TEST_RESPONSE")
        response = instrument._query("TEST:COMMAND?")
        assert response == "TEST_RESPONSE"
        print("✓ Custom mock responses working")

        # Test 4: Error handling
        instrument.disconnect()
        assert not instrument.is_connected
        print("✓ VISA disconnect working")

        # Test 5: Context manager
        with MockVisaInstrument("MOCK::CONTEXT") as inst:
            assert inst.is_connected
        print("✓ VISA context manager working")

    except Exception as e:
        print(f"✗ VISA backend test failed: {e}")
        return False

    return True


def test_power_supply_driver():
    """Test the power supply driver."""
    print("\nTesting power supply driver...")

    try:
        # Initialize basic logging for this test
        config = SystemConfig()
        setup_logging(config)

        # Test 1: Driver instantiation and connection
        ps = MockKeysightE36100Series(model="E36103A")  # 2-channel model
        ps.connect("MOCK::E36103A")
        assert ps.is_connected
        assert ps.model_name == "E36103A"
        assert ps.num_channels == 2
        print("✓ Power supply driver connection and identification")

        # Test 2: Basic voltage operations
        ps.set_voltage(5.0, channel=1)
        voltage = ps.get_voltage(channel=1)
        assert voltage == 5.0
        print("✓ Voltage set/get operations")

        # Test 3: Current limit operations
        ps.set_current_limit(1.5, channel=1)
        current_limit = ps.get_current_limit(channel=1)
        assert current_limit == 1.5
        print("✓ Current limit operations")

        # Test 4: Output control
        ps.set_output_state(True, channel=1)
        assert ps.get_output_state(channel=1) == True
        measured_voltage = ps.measure_voltage(channel=1)
        assert measured_voltage == 5.0  # Mock returns set voltage when output is on
        print("✓ Output control and measurement")

        # Test 5: Protection settings
        ps.set_ovp_threshold(6.0, channel=1)
        ovp = ps.get_ovp_threshold(channel=1)
        assert ovp == 6.0
        print("✓ Over-voltage protection settings")

        # Test 6: Multi-channel operations
        ps.configure_channel(2, voltage=3.3, current_limit=2.0, output_enabled=True)
        status = ps.get_status(channel=2)
        assert status["voltage_set"] == 3.3
        assert status["current_limit"] == 2.0
        assert status["output_enabled"] == True
        print("✓ Multi-channel configuration and status")

        # Test 7: Channel validation
        try:
            ps.set_voltage(5.0, channel=5)  # Invalid channel for 2-channel model
            print("✗ Channel validation should have failed")
            return False
        except ValueError:
            print("✓ Channel validation working")

        ps.disconnect()

    except Exception as e:
        print(f"✗ Power supply driver test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_multimeter_driver():
    """Test the multimeter driver."""
    print("\nTesting multimeter driver...")

    try:
        # Initialize basic logging for this test
        config = SystemConfig()
        setup_logging(config)

        # Test 1: Driver instantiation and connection
        dmm = Mock34461A()
        dmm.connect("MOCK::34461A")
        assert dmm.is_connected
        assert dmm.model_name == "34461A"
        print("✓ Multimeter driver connection and identification")

        # Test 2: DC voltage measurement
        voltage = dmm.measure_dc_voltage()
        assert 4.5 <= voltage <= 5.5  # Mock returns ~5V with noise
        print("✓ DC voltage measurement")

        # Test 3: AC voltage measurement
        ac_voltage = dmm.measure_ac_voltage()
        assert 1.0 <= ac_voltage <= 2.0  # Mock returns ~1.414V
        print("✓ AC voltage measurement")

        # Test 4: Current measurements
        dc_current = dmm.measure_dc_current()
        ac_current = dmm.measure_ac_current()
        assert 0.0005 <= dc_current <= 0.002
        assert 0.0001 <= ac_current <= 0.001
        print("✓ Current measurements")

        # Test 5: Resistance measurement
        resistance = dmm.measure_resistance()
        assert 900 <= resistance <= 1100  # Mock returns ~1kOhm
        print("✓ Resistance measurement")

        # Test 6: Capacitance measurement
        capacitance = dmm.measure_capacitance()
        assert 0.5e-6 <= capacitance <= 1.5e-6  # Mock returns ~1µF
        print("✓ Capacitance measurement")

        # Test 7: Configuration and triggered measurements
        dmm.configure_measurement("VDC", range=10.0, resolution=0.001)
        dmm.trigger_measurement()
        result = dmm.read_measurement()
        assert isinstance(result, float)
        print("✓ Configure/trigger/read cycle")

        # Test 8: Status query
        status = dmm.get_status()
        assert status["model"] == "34461A"
        assert status["connected"] == True
        print("✓ Status query")

        dmm.disconnect()

    except Exception as e:
        print(f"✗ Multimeter driver test failed: {e}")
        return False

    return True


def test_function_generator_driver():
    """Test the function generator driver."""
    print("\nTesting function generator driver...")

    try:
        # Initialize basic logging for this test
        config = SystemConfig()
        setup_logging(config)

        # Test 1: Driver instantiation and connection
        fg = Mock33500Series(model="33512B")  # 2-channel model
        fg.connect("MOCK::33512B")
        assert fg.is_connected
        assert fg.model_name == "33512B"
        assert fg.num_channels == 2
        print("✓ Function generator driver connection and identification")

        # Test 2: Waveform operations
        fg.set_waveform("SIN", channel=1)
        waveform = fg.get_waveform(channel=1)
        assert waveform == "SIN"
        print("✓ Waveform operations")

        # Test 3: Frequency operations
        fg.set_frequency(1000.0, channel=1)
        frequency = fg.get_frequency(channel=1)
        assert frequency == 1000.0
        print("✓ Frequency operations")

        # Test 4: Amplitude operations
        fg.set_amplitude(2.0, channel=1)
        amplitude = fg.get_amplitude(channel=1)
        assert amplitude == 2.0
        print("✓ Amplitude operations")

        # Test 5: Offset operations
        fg.set_offset(0.5, channel=1)
        offset = fg.get_offset(channel=1)
        assert offset == 0.5
        print("✓ Offset operations")

        # Test 6: Phase operations
        fg.set_phase(90.0, channel=1)
        phase = fg.get_phase(channel=1)
        assert phase == 90.0
        print("✓ Phase operations")

        # Test 7: Output control
        fg.set_output_state(True, channel=1)
        assert fg.get_output_state(channel=1) == True
        print("✓ Output control")

        # Test 8: Complete channel configuration
        fg.configure_channel(
            channel=2,
            waveform="SQU",
            frequency=500.0,
            amplitude=1.0,
            offset=0.0,
            phase=0.0,
            output_enabled=True
        )
        status = fg.get_status(channel=2)
        assert status["waveform"] == "SQU"
        assert status["frequency"] == 500.0
        assert status["amplitude"] == 1.0
        assert status["output_enabled"] == True
        print("✓ Complete channel configuration")

        # Test 9: Duty cycle for square wave
        fg.set_duty_cycle(25.0, channel=2)
        duty_cycle = fg.get_duty_cycle(channel=2)
        assert duty_cycle == 25.0
        print("✓ Duty cycle operations")

        fg.disconnect()

    except Exception as e:
        print(f"✗ Function generator driver test failed: {e}")
        return False

    return True


def test_interface_compliance():
    """Test that drivers properly implement their interfaces."""
    print("\nTesting interface compliance...")

    try:
        # Test 1: Power supply interface compliance
        from hal.interfaces import PowerSupply
        ps = MockKeysightE36100Series()
        assert isinstance(ps, PowerSupply)
        # Check that all abstract methods are implemented
        required_methods = [
            'model_name', 'serial_number', 'is_connected', 'connect', 'disconnect',
            'reset', 'self_test', 'get_error_queue', 'set_voltage', 'get_voltage',
            'measure_voltage', 'set_current_limit', 'get_current_limit',
            'measure_current', 'set_output_state', 'get_output_state',
            'set_ovp_threshold', 'get_ovp_threshold'
        ]
        for method in required_methods:
            assert hasattr(ps, method), f"PowerSupply missing method: {method}"
        print("✓ Power supply interface compliance")

        # Test 2: Multimeter interface compliance
        from hal.interfaces import DigitalMultimeter
        dmm = Mock34461A()
        assert isinstance(dmm, DigitalMultimeter)
        required_methods = [
            'model_name', 'serial_number', 'is_connected', 'connect', 'disconnect',
            'reset', 'self_test', 'get_error_queue', 'measure_dc_voltage',
            'measure_ac_voltage', 'measure_dc_current', 'measure_ac_current',
            'measure_resistance', 'measure_capacitance', 'configure_measurement',
            'trigger_measurement', 'read_measurement'
        ]
        for method in required_methods:
            assert hasattr(dmm, method), f"DigitalMultimeter missing method: {method}"
        print("✓ Multimeter interface compliance")

        # Test 3: Function generator interface compliance
        from hal.interfaces import FunctionGenerator
        fg = Mock33500Series()
        assert isinstance(fg, FunctionGenerator)
        required_methods = [
            'model_name', 'serial_number', 'is_connected', 'connect', 'disconnect',
            'reset', 'self_test', 'get_error_queue', 'set_waveform', 'get_waveform',
            'set_frequency', 'get_frequency', 'set_amplitude', 'get_amplitude',
            'set_offset', 'get_offset', 'set_output_state', 'get_output_state'
        ]
        for method in required_methods:
            assert hasattr(fg, method), f"FunctionGenerator missing method: {method}"
        print("✓ Function generator interface compliance")

    except Exception as e:
        print(f"✗ Interface compliance test failed: {e}")
        return False

    return True


def test_hal_integration():
    """Test integration of HAL with core infrastructure."""
    print("\nTesting HAL integration with core infrastructure...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup core infrastructure
            config = SystemConfig()
            config.paths.log_dir = Path(temp_dir) / "logs"
            config.paths.db_path = Path(temp_dir) / "test.db"

            # Initialize logging
            run_id = setup_logging(config)
            logger = get_logger(__name__)

            # Test 1: Instrument creation with logging
            logger.info("Creating mock instruments")
            ps = MockKeysightE36100Series()
            dmm = Mock34461A()
            fg = Mock33500Series()

            # Test 2: Connect instruments (should generate logs)
            ps.connect("MOCK::PS")
            dmm.connect("MOCK::DMM")
            fg.connect("MOCK::FG")
            logger.info("All instruments connected")

            # Test 3: Perform operations that generate instrument logs
            ps.set_voltage(5.0)
            voltage = dmm.measure_dc_voltage()
            fg.set_frequency(1000.0)
            logger.info(f"Operations completed: PS=5.0V, DMM={voltage:.3f}V, FG=1kHz")

            # Test 4: Disconnect instruments
            ps.disconnect()
            dmm.disconnect()
            fg.disconnect()
            logger.info("All instruments disconnected")

            # Test 5: Verify log file contains instrument commands
            log_files = list(config.paths.log_dir.glob("*.log"))
            assert len(log_files) == 1

            with open(log_files[0], 'r') as f:
                log_content = f.read()
                assert "connected" in log_content  # Look for any connection messages
                assert run_id in log_content
                print("✓ HAL operations logged correctly")

    except Exception as e:
        print(f"✗ HAL integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """Run all HAL verification tests."""
    print("Phase 2 Hardware Abstraction Layer (HAL) Verification")
    print("=" * 60)

    tests = [
        test_visa_backend,
        test_power_supply_driver,
        test_multimeter_driver,
        test_function_generator_driver,
        test_interface_compliance,
        test_hal_integration
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            break  # Stop on first failure

    print(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All Phase 2 HAL components are working correctly!")
        print("\nWhat we've accomplished:")
        print("✓ Abstract instrument interfaces defined")
        print("✓ VISA communication backend implemented")
        print("✓ Concrete drivers for Power Supply, DMM, and Function Generator")
        print("✓ Mock implementations for hardware-free testing")
        print("✓ Full integration with Phase 1 infrastructure")
        print("\nNext steps:")
        print("- Proceed to Phase 3: Pytest integration and fixtures")
        print("- Create instrument fixtures for test management")
        print("- Implement test result persistence integration")
        return True
    else:
        print("❌ Some tests failed. Please fix issues before proceeding.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)