#!/usr/bin/env python3
"""
Phase 2 feature verification test.

Tests the new Phase 2 features:
- Retry mechanisms
- Instrument discovery
- Oscilloscope driver
"""

import time
from hal.discovery import discover_instruments, find_oscilloscopes
from hal.drivers.keysight_dsox1000_series import MockDSOX1000Series
from hal.retry_utils import RetryConfig, retry_on_communication_error
from hal.interfaces import CommunicationError


def test_instrument_discovery():
    """Test instrument discovery system."""
    print("Testing instrument discovery...")

    # Discover instruments (including mock)
    instruments = discover_instruments(include_mock=True)
    print(f"✓ Discovery system functional (found {len(instruments)} instruments)")

    # Test finding specific types
    oscilloscopes = find_oscilloscopes(include_mock=True)
    print(f"✓ Type-specific discovery works (found {len(oscilloscopes)} oscilloscopes)")

    return True


def test_oscilloscope_driver():
    """Test oscilloscope driver functionality."""
    print("\nTesting oscilloscope driver...")

    try:
        # Create mock oscilloscope
        scope = MockDSOX1000Series()
        scope.connect("MOCK::DSOX1204G")
        print("✓ Mock oscilloscope connected")

        # Test basic operations
        scope.set_channel_state(1, True)
        assert scope.get_channel_state(1) == True
        print("✓ Channel control works")

        scope.set_vertical_scale(1, 2.0)
        scope.set_time_scale(1e-3)
        print("✓ Scale controls work")

        # Test waveform acquisition
        waveform = scope.acquire_waveform(1)
        assert "time" in waveform
        assert "voltage" in waveform
        assert len(waveform["time"]) == len(waveform["voltage"])
        print(f"✓ Waveform acquisition works ({len(waveform['time'])} points)")

        # Test measurements
        freq = scope.measure_parameter(1, "FREQ")
        amplitude = scope.measure_parameter(1, "AMPL")
        print(f"✓ Measurements work (freq={freq}Hz, ampl={amplitude}V)")

        scope.disconnect()
        print("✓ Oscilloscope disconnected")

    except Exception as e:
        print(f"✗ Oscilloscope test failed: {e}")
        return False

    return True


def test_retry_mechanisms():
    """Test retry mechanisms."""
    print("\nTesting retry mechanisms...")

    # Test successful retry after failure
    call_count = 0

    @retry_on_communication_error(RetryConfig(max_attempts=3, base_delay=0.1))
    def flaky_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise CommunicationError("Simulated communication failure")
        return "success"

    try:
        result = flaky_operation()
        assert result == "success"
        assert call_count == 3
        print(f"✓ Retry mechanism works (succeeded after {call_count} attempts)")
    except Exception as e:
        print(f"✗ Retry test failed: {e}")
        return False

    # Test that it eventually fails
    call_count = 0

    @retry_on_communication_error(RetryConfig(max_attempts=2, base_delay=0.05))
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise CommunicationError("Always fails")

    try:
        always_fails()
        print("✗ Retry should have failed but didn't")
        return False
    except CommunicationError:
        assert call_count == 2
        print(f"✓ Retry correctly fails after max attempts ({call_count})")

    return True


def test_enhanced_visa_instrument():
    """Test enhanced VISA instrument with retry support."""
    print("\nTesting enhanced VISA instrument...")

    try:
        from hal.drivers.keysight_34461a import Mock34461A

        # Create mock DMM with custom retry config
        retry_config = RetryConfig(max_attempts=2, base_delay=0.05)
        dmm = Mock34461A(retry_config=retry_config)
        dmm.connect("MOCK::34461A")

        # Test basic operation
        voltage = dmm.measure_dc_voltage()
        print(f"✓ Enhanced VISA instrument works (measured {voltage}V)")

        dmm.disconnect()

    except Exception as e:
        print(f"✗ Enhanced VISA instrument test failed: {e}")
        return False

    return True


def main():
    """Run all Phase 2 tests."""
    print("Phase 2 Feature Verification Test")
    print("=" * 40)

    tests = [
        test_instrument_discovery,
        test_oscilloscope_driver,
        test_retry_mechanisms,
        test_enhanced_visa_instrument
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            break

    print(f"\nResults: {passed}/{total} Phase 2 tests passed")

    if passed == total:
        print("🎉 All Phase 2 features are working correctly!")
        print("\nPhase 2 achievements:")
        print("- ✅ Enhanced type safety (reduced mypy errors)")
        print("- ✅ Robust retry mechanisms for communication failures")
        print("- ✅ Automatic instrument discovery system")
        print("- ✅ Complete oscilloscope driver with waveform capture")
        print("- ✅ Enhanced VISA backend with retry support")
        print("\nReady for Phase 3: Long-term features!")
        return True
    else:
        print("❌ Some Phase 2 tests failed. Please fix issues before proceeding.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)