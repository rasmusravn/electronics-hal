"""
Integration tests for function generator waveform generation.

These tests verify waveform generation accuracy, frequency stability,
and signal integrity across different waveform types.
"""

import math
import time

import pytest

from hal.interfaces import DigitalMultimeter, FunctionGenerator


class TestWaveformGeneration:
    """Test waveform generation capabilities of function generators."""

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_basic_sine_wave_generation(
        self,
        mock_function_generator: FunctionGenerator,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test basic sine wave generation and measurement."""
        # Configure sine wave
        frequency = 1000.0  # 1 kHz
        amplitude = 2.0     # 2V peak-to-peak
        offset = 0.0        # No DC offset

        mock_function_generator.configure_channel(
            channel=1,
            waveform="SIN",
            frequency=frequency,
            amplitude=amplitude,
            offset=offset,
            output_enabled=True
        )

        # Allow signal to stabilize
        time.sleep(0.1)

        # Measure AC voltage (RMS)
        measured_ac = mock_multimeter.measure_ac_voltage()
        expected_rms = amplitude / (2 * math.sqrt(2))  # Vpp to RMS conversion

        # Measure DC component (should be close to offset)
        measured_dc = mock_multimeter.measure_dc_voltage()

        # Log measurements
        test_logger.log_measurement(
            name="sine_wave_amplitude",
            value=measured_ac,
            unit="V_RMS",
            limits={"min": expected_rms - 0.01, "max": expected_rms + 0.01},
            frequency=frequency,
            amplitude_setting=amplitude,
            expected_rms=expected_rms
        )

        test_logger.log_measurement(
            name="sine_wave_dc_offset",
            value=measured_dc,
            unit="V",
            limits={"min": offset - 0.01, "max": offset + 0.01},
            offset_setting=offset
        )

        # Verify measurements
        assert abs(measured_ac - expected_rms) <= 0.01, \
            f"AC amplitude {measured_ac:.4f}V RMS != expected {expected_rms:.4f}V RMS"
        assert abs(measured_dc - offset) <= 0.01, \
            f"DC offset {measured_dc:.4f}V != expected {offset:.4f}V"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    @pytest.mark.parametrize(
        "waveform,frequency,amplitude,expected_rms_factor",
        [
            ("SIN", 1000.0, 2.0, 1/(2*math.sqrt(2))),    # Sine wave RMS factor
            ("SQU", 1000.0, 2.0, 0.5),                   # Square wave RMS factor
            ("TRI", 1000.0, 2.0, 1/(2*math.sqrt(3))),    # Triangle wave RMS factor
        ],
    )
    def test_multiple_waveform_types(
        self,
        waveform: str,
        frequency: float,
        amplitude: float,
        expected_rms_factor: float,
        mock_function_generator: FunctionGenerator,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test generation of different waveform types."""
        # Configure function generator
        mock_function_generator.configure_channel(
            channel=1,
            waveform=waveform,
            frequency=frequency,
            amplitude=amplitude,
            offset=0.0,
            output_enabled=True
        )

        time.sleep(0.1)

        # Measure signal
        measured_rms = mock_multimeter.measure_ac_voltage()
        expected_rms = amplitude * expected_rms_factor

        # Calculate tolerance based on waveform type
        tolerance = 0.02 if waveform == "SIN" else 0.05  # Looser tolerance for non-sine

        test_logger.log_measurement(
            name=f"{waveform.lower()}_wave_rms",
            value=measured_rms,
            unit="V_RMS",
            limits={"min": expected_rms - tolerance, "max": expected_rms + tolerance},
            waveform=waveform,
            frequency=frequency,
            amplitude=amplitude,
            expected_rms=expected_rms
        )

        # Verify measurement
        assert abs(measured_rms - expected_rms) <= tolerance, \
            f"{waveform} wave RMS {measured_rms:.4f}V != expected {expected_rms:.4f}V"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_frequency_accuracy(
        self,
        mock_function_generator: FunctionGenerator,
        test_logger
    ):
        """Test frequency accuracy across different frequency ranges."""
        test_frequencies = [100.0, 1000.0, 10000.0, 100000.0]  # 100Hz to 100kHz

        for freq in test_frequencies:
            # Configure generator
            mock_function_generator.configure_channel(
                channel=1,
                waveform="SQU",  # Square wave for easier frequency measurement
                frequency=freq,
                amplitude=2.0,
                output_enabled=True
            )

            time.sleep(0.1)

            # Get actual frequency setting from generator
            actual_freq = mock_function_generator.get_frequency(1)

            # Calculate frequency error
            freq_error = actual_freq - freq
            freq_error_ppm = (freq_error / freq) * 1e6

            # Tolerance depends on frequency range
            if freq < 1000:
                tolerance_ppm = 100  # ±100 ppm for low frequencies
            else:
                tolerance_ppm = 50   # ±50 ppm for higher frequencies

            tolerance_hz = freq * tolerance_ppm / 1e6

            test_logger.log_measurement(
                name=f"frequency_{freq}Hz",
                value=actual_freq,
                unit="Hz",
                limits={"min": freq - tolerance_hz, "max": freq + tolerance_hz},
                target_frequency=freq,
                error_ppm=freq_error_ppm,
                tolerance_ppm=tolerance_ppm
            )

            # Verify frequency accuracy
            assert abs(freq_error_ppm) <= tolerance_ppm, \
                f"Frequency error {freq_error_ppm:.1f} ppm exceeds ±{tolerance_ppm} ppm"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_amplitude_control(
        self,
        mock_function_generator: FunctionGenerator,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test amplitude control accuracy."""
        frequency = 1000.0
        amplitudes = [0.1, 0.5, 1.0, 2.0, 5.0]  # Different amplitude levels

        for amplitude in amplitudes:
            # Configure generator
            mock_function_generator.configure_channel(
                channel=1,
                waveform="SIN",
                frequency=frequency,
                amplitude=amplitude,
                offset=0.0,
                output_enabled=True
            )

            time.sleep(0.1)

            # Measure AC voltage
            measured_rms = mock_multimeter.measure_ac_voltage()
            expected_rms = amplitude / (2 * math.sqrt(2))

            # Tolerance: ±2% or ±1mV, whichever is larger
            tolerance = max(expected_rms * 0.02, 0.001)

            test_logger.log_measurement(
                name=f"amplitude_{amplitude}Vpp",
                value=measured_rms,
                unit="V_RMS",
                limits={"min": expected_rms - tolerance, "max": expected_rms + tolerance},
                amplitude_setting=amplitude,
                expected_rms=expected_rms,
                tolerance_percent=(tolerance / expected_rms) * 100
            )

            # Verify amplitude accuracy
            error = abs(measured_rms - expected_rms)
            assert error <= tolerance, \
                f"Amplitude error {error:.4f}V RMS exceeds ±{tolerance:.4f}V RMS"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_dc_offset_control(
        self,
        mock_function_generator: FunctionGenerator,
        mock_multimeter: DigitalMultimeter,
        test_logger
    ):
        """Test DC offset control accuracy."""
        offsets = [-1.0, -0.5, 0.0, 0.5, 1.0]  # Different offset levels

        for offset in offsets:
            # Configure with small AC signal + DC offset
            mock_function_generator.configure_channel(
                channel=1,
                waveform="SIN",
                frequency=1000.0,
                amplitude=0.1,  # Small AC component
                offset=offset,
                output_enabled=True
            )

            time.sleep(0.1)

            # Measure DC component
            measured_dc = mock_multimeter.measure_dc_voltage()

            tolerance = 0.01  # ±10mV

            test_logger.log_measurement(
                name=f"dc_offset_{offset}V",
                value=measured_dc,
                unit="V",
                limits={"min": offset - tolerance, "max": offset + tolerance},
                offset_setting=offset
            )

            # Verify offset accuracy
            error = abs(measured_dc - offset)
            assert error <= tolerance, \
                f"Offset error {error:.4f}V exceeds ±{tolerance:.4f}V"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_square_wave_duty_cycle(
        self,
        mock_function_generator: FunctionGenerator,
        test_logger
    ):
        """Test square wave duty cycle control."""
        duty_cycles = [25.0, 50.0, 75.0]  # Different duty cycles

        for duty_cycle in duty_cycles:
            # Configure square wave
            mock_function_generator.configure_channel(
                channel=1,
                waveform="SQU",
                frequency=1000.0,
                amplitude=2.0,
                output_enabled=True
            )

            # Set duty cycle
            mock_function_generator.set_duty_cycle(duty_cycle, 1)

            time.sleep(0.1)

            # Get actual duty cycle setting
            actual_duty_cycle = mock_function_generator.get_duty_cycle(1)

            tolerance = 1.0  # ±1%

            test_logger.log_measurement(
                name=f"duty_cycle_{duty_cycle}percent",
                value=actual_duty_cycle,
                unit="%",
                limits={"min": duty_cycle - tolerance, "max": duty_cycle + tolerance},
                target_duty_cycle=duty_cycle
            )

            # Verify duty cycle setting
            error = abs(actual_duty_cycle - duty_cycle)
            assert error <= tolerance, \
                f"Duty cycle error {error:.1f}% exceeds ±{tolerance:.1f}%"

    @pytest.mark.integration
    @pytest.mark.signal_generation
    def test_multi_channel_operation(
        self,
        mock_function_generator: FunctionGenerator,
        test_logger
    ):
        """Test independent operation of multiple channels."""
        # Skip if single-channel generator
        if mock_function_generator.num_channels < 2:
            pytest.skip("Test requires multi-channel function generator")

        # Configure different signals on each channel
        ch1_config = {
            "waveform": "SIN",
            "frequency": 1000.0,
            "amplitude": 2.0,
            "offset": 0.0
        }

        ch2_config = {
            "waveform": "SQU",
            "frequency": 2000.0,
            "amplitude": 1.0,
            "offset": 0.5
        }

        # Configure both channels
        mock_function_generator.configure_channel(1, output_enabled=True, **ch1_config)
        mock_function_generator.configure_channel(2, output_enabled=True, **ch2_config)

        time.sleep(0.1)

        # Verify each channel configuration
        for ch, config in [(1, ch1_config), (2, ch2_config)]:
            actual_freq = mock_function_generator.get_frequency(ch)
            actual_amp = mock_function_generator.get_amplitude(ch)
            actual_offset = mock_function_generator.get_offset(ch)
            actual_waveform = mock_function_generator.get_waveform(ch)

            test_logger.log_measurement(
                name=f"ch{ch}_frequency_check",
                value=actual_freq,
                unit="Hz",
                limits={"min": config["frequency"] - 1, "max": config["frequency"] + 1},
                channel=ch,
                target=config["frequency"]
            )

            test_logger.log_measurement(
                name=f"ch{ch}_amplitude_check",
                value=actual_amp,
                unit="V",
                limits={"min": config["amplitude"] - 0.01, "max": config["amplitude"] + 0.01},
                channel=ch,
                target=config["amplitude"]
            )

            # Verify settings are correct
            assert abs(actual_freq - config["frequency"]) <= 1.0
            assert abs(actual_amp - config["amplitude"]) <= 0.01
            assert abs(actual_offset - config["offset"]) <= 0.01
            assert actual_waveform == config["waveform"]

        # Test channel independence: modify channel 1, check channel 2 unchanged
        new_freq = 1500.0
        mock_function_generator.set_frequency(new_freq, 1)

        time.sleep(0.05)

        ch1_freq_after = mock_function_generator.get_frequency(1)
        ch2_freq_after = mock_function_generator.get_frequency(2)

        test_logger.log_measurement(
            name="ch1_frequency_after_change",
            value=ch1_freq_after,
            unit="Hz",
            limits={"min": new_freq - 1, "max": new_freq + 1},
            channel=1,
            new_frequency=new_freq
        )

        test_logger.log_measurement(
            name="ch2_frequency_independence",
            value=ch2_freq_after,
            unit="Hz",
            limits={"min": ch2_config["frequency"] - 1, "max": ch2_config["frequency"] + 1},
            channel=2,
            expected=ch2_config["frequency"],
            test_type="independence"
        )

        # Verify channel 1 changed and channel 2 remained unchanged
        assert abs(ch1_freq_after - new_freq) <= 1.0
        assert abs(ch2_freq_after - ch2_config["frequency"]) <= 1.0
