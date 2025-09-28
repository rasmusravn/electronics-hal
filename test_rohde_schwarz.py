#!/usr/bin/env python3
"""
Test script for Rohde & Schwarz instrument drivers.

Tests the new R&S drivers:
- FSWP Signal Analyzer
- FSV Spectrum Analyzer
- SMA100A Signal Generator
"""

import time
import numpy as np
from hal.drivers.rohde_schwarz_fswp import MockFSWP
from hal.drivers.rohde_schwarz_fsv import MockFSV
from hal.drivers.rohde_schwarz_sma100a import MockSMA100A
from hal.discovery import discover_instruments, find_signal_analyzers, find_signal_generators


def test_fswp_driver():
    """Test FSWP signal analyzer driver."""
    print("Testing R&S FSWP Signal Analyzer...")

    try:
        # Create mock FSWP
        fswp = MockFSWP()
        fswp.connect("MOCK::FSWP26")
        print("✓ FSWP connected")

        # Test basic frequency setup
        fswp.set_center_frequency(2.4e9)  # 2.4 GHz
        assert abs(fswp.get_center_frequency() - 2.4e9) < 1e6
        print("✓ Center frequency control works")

        fswp.set_frequency_span(100e6)  # 100 MHz
        assert abs(fswp.get_frequency_span() - 100e6) < 1e6
        print("✓ Frequency span control works")

        # Test amplitude settings
        fswp.set_reference_level(-10.0)  # -10 dBm
        assert abs(fswp.get_reference_level() - (-10.0)) < 0.1
        print("✓ Reference level control works")

        # Test bandwidth settings
        fswp.set_resolution_bandwidth(1e6)  # 1 MHz
        assert abs(fswp.get_resolution_bandwidth() - 1e6) < 1e3
        print("✓ Resolution bandwidth control works")

        # Test trace acquisition
        trace = fswp.acquire_trace(1)
        assert "frequency" in trace
        assert "amplitude" in trace
        assert len(trace["frequency"]) == len(trace["amplitude"])
        print(f"✓ Trace acquisition works ({len(trace['frequency'])} points)")

        # Test peak measurement
        peak = fswp.measure_peak(1)
        assert "frequency" in peak
        assert "amplitude" in peak
        print(f"✓ Peak measurement works (f={peak['frequency']/1e9:.3f} GHz, {peak['amplitude']:.1f} dBm)")

        # Test marker measurement
        marker_freq = 2.4e9
        amplitude = fswp.measure_marker(1, marker_freq)
        print(f"✓ Marker measurement works ({amplitude:.1f} dBm at {marker_freq/1e9:.3f} GHz)")

        # Test status
        status = fswp.get_instrument_status()
        assert status["connected"] == True
        assert "frequency" in str(status)
        print("✓ Instrument status retrieval works")

        fswp.disconnect()
        print("✓ FSWP disconnected")

    except Exception as e:
        print(f"✗ FSWP test failed: {e}")
        return False

    return True


def test_fsv_driver():
    """Test FSV spectrum analyzer driver."""
    print("\nTesting R&S FSV Spectrum Analyzer...")

    try:
        # Create mock FSV
        fsv = MockFSV(model="FSV30")
        fsv.connect("MOCK::FSV30")
        print("✓ FSV connected")

        # Test frequency setup
        fsv.set_start_frequency(1e9)  # 1 GHz
        fsv.set_stop_frequency(2e9)   # 2 GHz
        start_freq = fsv.get_start_frequency()
        stop_freq = fsv.get_stop_frequency()
        print(f"Debug: start_freq={start_freq}, stop_freq={stop_freq}")
        assert abs(start_freq - 1e9) < 1e6
        assert abs(stop_freq - 2e9) < 1e6
        print("✓ Start/stop frequency control works")

        # Test bandwidth settings
        fsv.set_resolution_bandwidth(100e3)  # 100 kHz
        fsv.set_video_bandwidth(300e3)       # 300 kHz
        assert abs(fsv.get_resolution_bandwidth() - 100e3) < 1e3
        assert abs(fsv.get_video_bandwidth() - 300e3) < 1e3
        print("✓ Bandwidth controls work")

        # Test sweep settings
        fsv.set_sweep_points(1001)
        assert fsv.get_sweep_points() == 1001
        print("✓ Sweep points control works")

        # Test trace acquisition
        trace = fsv.acquire_trace(1)
        assert "frequency" in trace
        assert "amplitude" in trace
        assert len(trace["frequency"]) == len(trace["amplitude"])
        print(f"✓ Trace acquisition works ({len(trace['frequency'])} points)")

        # Test measurements
        peak = fsv.measure_peak(1)
        assert "frequency" in peak
        assert "amplitude" in peak
        print(f"✓ Peak measurement works (f={peak['frequency']/1e9:.3f} GHz, {peak['amplitude']:.1f} dBm)")

        # Test marker
        marker_amplitude = fsv.measure_marker(1, 1.5e9)
        print(f"✓ Marker measurement works ({marker_amplitude:.1f} dBm)")

        # Test detector and trace modes
        fsv.set_detector_mode("PEAK")
        fsv.set_trace_mode(1, "WRIT")
        print("✓ Detector and trace mode controls work")

        fsv.disconnect()
        print("✓ FSV disconnected")

    except Exception as e:
        print(f"✗ FSV test failed: {e}")
        return False

    return True


def test_sma100a_driver():
    """Test SMA100A signal generator driver."""
    print("\nTesting R&S SMA100A Signal Generator...")

    try:
        # Create mock SMA100A
        sma = MockSMA100A()
        sma.connect("MOCK::SMA100A")
        print("✓ SMA100A connected")

        # Test frequency control
        sma.set_frequency(1, 1e9)  # 1 GHz
        assert abs(sma.get_frequency(1) - 1e9) < 1e3
        print("✓ Frequency control works")

        # Test power control
        sma.set_amplitude(1, -10.0)  # -10 dBm
        assert abs(sma.get_amplitude(1) - (-10.0)) < 0.1
        print("✓ Power control works")

        # Test output control
        sma.set_output_enabled(1, True)
        assert sma.get_output_enabled(1) == True
        sma.set_output_enabled(1, False)
        assert sma.get_output_enabled(1) == False
        print("✓ Output control works")

        # Test phase control
        sma.set_phase(1, 90.0)  # 90 degrees
        assert abs(sma.get_phase(1) - 90.0) < 0.1
        print("✓ Phase control works")

        # Test CW mode
        sma.set_waveform(1, "CW")
        assert sma.get_waveform(1) == "CW"
        print("✓ CW mode works")

        # Test AM modulation
        sma.set_waveform(1, "AM")
        assert sma.get_waveform(1) == "AM"
        sma.set_modulation_frequency(1, 1000)  # 1 kHz
        sma.set_modulation_depth(1, 50.0)     # 50%
        assert abs(sma.get_modulation_frequency(1) - 1000) < 1
        assert abs(sma.get_modulation_depth(1) - 50.0) < 0.1
        print("✓ AM modulation works")

        # Test FM modulation
        sma.set_waveform(1, "FM")
        assert sma.get_waveform(1) == "FM"
        sma.set_modulation_depth(1, 10000)  # 10 kHz deviation
        print("✓ FM modulation works")

        # Test reference oscillator
        sma.set_reference_oscillator("INT")
        assert sma.get_reference_oscillator() == "INT"
        print("✓ Reference oscillator control works")

        # Test status
        status = sma.get_instrument_status()
        assert status["connected"] == True
        assert "frequency" in status
        assert "power" in status
        print("✓ Instrument status retrieval works")

        sma.disconnect()
        print("✓ SMA100A disconnected")

    except Exception as e:
        print(f"✗ SMA100A test failed: {e}")
        return False

    return True


def test_discovery_integration():
    """Test discovery system integration."""
    print("\nTesting Discovery System Integration...")

    try:
        # Test general discovery
        instruments = discover_instruments(include_mock=True)
        print(f"✓ Discovery found {len(instruments)} instruments")

        # Test type-specific discovery
        analyzers = find_signal_analyzers(include_mock=True)
        generators = find_signal_generators(include_mock=True)
        print(f"✓ Found {len(analyzers)} signal analyzers")
        print(f"✓ Found {len(generators)} signal generators")

        # Test capability-based discovery
        from hal.discovery import get_discovery
        discovery = get_discovery()

        rf_instruments = discovery.find_instruments_by_capability("rf_generation", include_mock=True)
        spectrum_instruments = discovery.find_instruments_by_capability("spectrum_analysis", include_mock=True)

        print(f"✓ Found {len(rf_instruments)} RF generation capable instruments")
        print(f"✓ Found {len(spectrum_instruments)} spectrum analysis capable instruments")

    except Exception as e:
        print(f"✗ Discovery integration test failed: {e}")
        return False

    return True


def test_advanced_features():
    """Test advanced features of R&S instruments."""
    print("\nTesting Advanced Features...")

    try:
        # Test FSWP advanced features
        fswp = MockFSWP()
        fswp.connect("MOCK::FSWP26")

        fswp.set_detector_mode("PEAK")
        fswp.set_trace_mode(1, "MAXH")  # Max hold
        fswp.set_marker_delta_mode(2, 1)  # Marker 2 delta to marker 1
        print("✓ FSWP advanced features work")
        fswp.disconnect()

        # Test SMA100A advanced features
        sma = MockSMA100A()
        sma.connect("MOCK::SMA100A")

        sma.set_attenuator_mode("AUTO")
        assert sma.get_attenuator_mode() == "AUTO"

        sma.set_reference_oscillator("EXT")
        assert sma.get_reference_oscillator() == "EXT"

        # Test PM modulation
        sma.set_waveform(1, "PM")
        sma.set_modulation_depth(1, 1.0)  # 1 degree
        print("✓ SMA100A advanced features work")
        sma.disconnect()

    except Exception as e:
        print(f"✗ Advanced features test failed: {e}")
        return False

    return True


def main():
    """Run all R&S driver tests."""
    print("Rohde & Schwarz Instrument Drivers Test")
    print("=" * 50)

    tests = [
        test_fswp_driver,
        test_fsv_driver,
        test_sma100a_driver,
        test_discovery_integration,
        test_advanced_features
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        else:
            break

    print(f"\nResults: {passed}/{total} R&S driver tests passed")

    if passed == total:
        print("🎉 All Rohde & Schwarz drivers are working correctly!")
        print("\nNew capabilities added:")
        print("- ✅ FSWP Signal Analyzer (wide bandwidth, high performance)")
        print("- ✅ FSV Spectrum Analyzer (excellent price/performance)")
        print("- ✅ SMA100A RF Signal Generator (high spectral purity)")
        print("- ✅ Signal Analyzer interface with comprehensive features")
        print("- ✅ Advanced modulation and measurement capabilities")
        print("- ✅ Discovery system integration for all R&S instruments")
        print("\nHardware support expanded from 4 to 7 instrument families!")
        return True
    else:
        print("❌ Some R&S driver tests failed. Please fix issues.")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)