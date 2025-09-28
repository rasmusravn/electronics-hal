"""
Behavioral models for realistic instrument simulation.

This module provides various behavioral models to simulate real-world
instrument characteristics including noise, drift, temperature effects,
and aging.
"""

import math
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class BehavioralModel(ABC):
    """Abstract base class for instrument behavioral models."""

    @abstractmethod
    def apply(self, base_value: float, context: Dict) -> float:
        """Apply behavioral modification to base value."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset model state."""
        pass


class NoiseModel(BehavioralModel):
    """Realistic noise modeling for instrument measurements."""

    def __init__(self, rms_noise: float = 0.001, frequency_noise: bool = True):
        """
        Initialize noise model.

        Args:
            rms_noise: RMS noise level relative to signal
            frequency_noise: Enable 1/f noise in addition to white noise
        """
        self.rms_noise = rms_noise
        self.frequency_noise = frequency_noise
        self._random = random.Random(42)
        self._pink_noise_state = 0.0

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply noise to measurement value."""
        # White noise (thermal noise)
        white_noise = self._random.gauss(0, self.rms_noise * abs(base_value))

        # Pink noise (1/f noise) - more prominent at low frequencies
        if self.frequency_noise:
            # Simple pink noise approximation
            self._pink_noise_state = 0.95 * self._pink_noise_state + 0.05 * self._random.gauss(0, 1)
            pink_noise = self._pink_noise_state * self.rms_noise * abs(base_value) * 0.3
        else:
            pink_noise = 0.0

        # Quantization noise for ADC simulation
        measurement_range = context.get('measurement_range', abs(base_value) * 2)
        bits = context.get('adc_bits', 16)
        quantization_step = measurement_range / (2 ** bits)
        quantization_noise = self._random.uniform(-0.5, 0.5) * quantization_step

        total_noise = white_noise + pink_noise + quantization_noise
        return base_value + total_noise

    def reset(self) -> None:
        """Reset noise model state."""
        self._pink_noise_state = 0.0


class DriftModel(BehavioralModel):
    """Temperature and time-based drift modeling."""

    def __init__(self, temp_coefficient: float = 100e-6, aging_rate: float = 1e-6):
        """
        Initialize drift model.

        Args:
            temp_coefficient: Temperature coefficient in ppm/°C
            aging_rate: Aging rate in ppm per hour
        """
        self.temp_coefficient = temp_coefficient
        self.aging_rate = aging_rate
        self.reference_temp = 23.0  # Reference temperature in °C
        self.start_time = datetime.utcnow()
        self._random = random.Random(42)

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply drift effects to measurement value."""
        # Temperature drift
        current_temp = context.get('temperature', 23.0)
        temp_drift = (current_temp - self.reference_temp) * self.temp_coefficient
        temp_effect = base_value * temp_drift

        # Aging drift (long-term stability)
        elapsed_hours = (datetime.utcnow() - self.start_time).total_seconds() / 3600
        aging_drift = elapsed_hours * self.aging_rate
        aging_effect = base_value * aging_drift

        # Add some randomness to drift
        drift_variation = self._random.gauss(0, self.temp_coefficient * 0.1)
        random_drift = base_value * drift_variation

        total_drift = temp_effect + aging_effect + random_drift
        return base_value + total_drift

    def reset(self) -> None:
        """Reset drift model state."""
        self.start_time = datetime.utcnow()


class NonlinearityModel(BehavioralModel):
    """Model instrument nonlinearity and calibration errors."""

    def __init__(self, linearity_error: float = 0.01, offset_error: float = 0.001):
        """
        Initialize nonlinearity model.

        Args:
            linearity_error: Maximum linearity error as fraction of full scale
            offset_error: Offset error as fraction of reading
        """
        self.linearity_error = linearity_error
        self.offset_error = offset_error
        self._random = random.Random(42)

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply nonlinearity effects."""
        full_scale = context.get('full_scale_range', abs(base_value) * 10)

        # Offset error
        offset = self.offset_error * full_scale * self._random.gauss(0, 0.3)

        # Linearity error (quadratic term)
        normalized_value = base_value / full_scale
        linearity_term = self.linearity_error * full_scale * (normalized_value ** 2)

        return base_value + offset + linearity_term

    def reset(self) -> None:
        """Reset nonlinearity model state."""
        pass


class FrequencyResponseModel(BehavioralModel):
    """Model frequency-dependent instrument behavior."""

    def __init__(self, bandwidth_3db: float = 1e6, rolloff_rate: float = 20):
        """
        Initialize frequency response model.

        Args:
            bandwidth_3db: 3dB bandwidth in Hz
            rolloff_rate: Rolloff rate in dB/decade beyond bandwidth
        """
        self.bandwidth_3db = bandwidth_3db
        self.rolloff_rate = rolloff_rate

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply frequency response effects."""
        frequency = context.get('frequency', 1000.0)

        if frequency <= self.bandwidth_3db:
            # Within bandwidth - minimal attenuation
            attenuation_db = 0.0
        else:
            # Beyond bandwidth - apply rolloff
            decades = math.log10(frequency / self.bandwidth_3db)
            attenuation_db = -self.rolloff_rate * decades

        # Convert dB to linear scale
        attenuation_linear = 10 ** (attenuation_db / 20)

        # Apply phase shift for reactive components
        phase_shift = math.atan(frequency / self.bandwidth_3db)
        context['phase_shift'] = phase_shift  # Store for potential use

        return base_value * attenuation_linear

    def reset(self) -> None:
        """Reset frequency response model state."""
        pass


class SettlingTimeModel(BehavioralModel):
    """Model instrument settling time and transient response."""

    def __init__(self, settling_time: float = 0.1, overshoot: float = 0.05):
        """
        Initialize settling time model.

        Args:
            settling_time: Time to settle to final value in seconds
            overshoot: Maximum overshoot as fraction of step
        """
        self.settling_time = settling_time
        self.overshoot = overshoot
        self.last_value = 0.0
        self.target_value = 0.0
        self.step_start_time = datetime.utcnow()

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply settling time effects."""
        current_time = datetime.utcnow()

        # Detect step change
        if abs(base_value - self.last_value) > abs(self.last_value) * 0.01:
            self.target_value = base_value
            self.step_start_time = current_time

        elapsed = (current_time - self.step_start_time).total_seconds()

        if elapsed < self.settling_time:
            # During settling period
            progress = elapsed / self.settling_time

            # Exponential approach with overshoot
            if progress < 0.3:
                # Initial overshoot
                overshoot_factor = 1 + self.overshoot * math.sin(progress * math.pi / 0.3)
            else:
                # Exponential settling
                overshoot_factor = 1 + self.overshoot * math.exp(-(progress - 0.3) * 5)

            # Exponential approach to target
            settle_factor = 1 - math.exp(-progress * 3)
            current_value = self.last_value + (self.target_value - self.last_value) * settle_factor * overshoot_factor

            self.last_value = current_value
            return current_value
        else:
            # Settled
            self.last_value = base_value
            return base_value

    def reset(self) -> None:
        """Reset settling time model state."""
        self.last_value = 0.0
        self.target_value = 0.0
        self.step_start_time = datetime.utcnow()


class CompositeModel(BehavioralModel):
    """Composite model that combines multiple behavioral models."""

    def __init__(self, models: List[BehavioralModel]):
        """Initialize with list of behavioral models."""
        self.models = models

    def apply(self, base_value: float, context: Dict) -> float:
        """Apply all models sequentially."""
        current_value = base_value

        for model in self.models:
            current_value = model.apply(current_value, context)

        return current_value

    def reset(self) -> None:
        """Reset all component models."""
        for model in self.models:
            model.reset()

    def add_model(self, model: BehavioralModel) -> None:
        """Add a behavioral model to the composite."""
        self.models.append(model)

    def remove_model(self, model_type: type) -> bool:
        """Remove first model of specified type."""
        for i, model in enumerate(self.models):
            if isinstance(model, model_type):
                del self.models[i]
                return True
        return False


class InstrumentProfile(BaseModel):
    """Predefined instrument behavioral profiles."""

    name: str = Field(..., description="Profile name")
    description: str = Field(..., description="Profile description")
    noise_rms: float = Field(default=0.001, description="RMS noise level")
    temp_coefficient: float = Field(default=100e-6, description="Temperature coefficient ppm/°C")
    settling_time: float = Field(default=0.1, description="Settling time in seconds")
    bandwidth_3db: float = Field(default=1e6, description="3dB bandwidth in Hz")
    linearity_error: float = Field(default=0.01, description="Linearity error fraction")

    def create_behavioral_model(self) -> CompositeModel:
        """Create behavioral model from profile parameters."""
        models = [
            NoiseModel(rms_noise=self.noise_rms),
            DriftModel(temp_coefficient=self.temp_coefficient),
            NonlinearityModel(linearity_error=self.linearity_error),
            FrequencyResponseModel(bandwidth_3db=self.bandwidth_3db),
            SettlingTimeModel(settling_time=self.settling_time)
        ]

        return CompositeModel(models)

    @classmethod
    def precision_multimeter(cls) -> "InstrumentProfile":
        """Profile for high-precision multimeter."""
        return cls(
            name="precision_multimeter",
            description="High-precision 7.5 digit multimeter",
            noise_rms=0.0001,
            temp_coefficient=10e-6,
            settling_time=0.5,
            bandwidth_3db=1e3,
            linearity_error=0.001
        )

    @classmethod
    def benchtop_dmm(cls) -> "InstrumentProfile":
        """Profile for standard benchtop DMM."""
        return cls(
            name="benchtop_dmm",
            description="Standard 6.5 digit benchtop multimeter",
            noise_rms=0.001,
            temp_coefficient=50e-6,
            settling_time=0.2,
            bandwidth_3db=1e4,
            linearity_error=0.005
        )

    @classmethod
    def handheld_dmm(cls) -> "InstrumentProfile":
        """Profile for handheld DMM."""
        return cls(
            name="handheld_dmm",
            description="Portable handheld multimeter",
            noise_rms=0.01,
            temp_coefficient=200e-6,
            settling_time=0.1,
            bandwidth_3db=1e3,
            linearity_error=0.02
        )

    @classmethod
    def oscilloscope(cls) -> "InstrumentProfile":
        """Profile for digital oscilloscope."""
        return cls(
            name="oscilloscope",
            description="Digital storage oscilloscope",
            noise_rms=0.002,
            temp_coefficient=100e-6,
            settling_time=0.01,
            bandwidth_3db=100e6,
            linearity_error=0.01
        )

    @classmethod
    def signal_generator(cls) -> "InstrumentProfile":
        """Profile for RF signal generator."""
        return cls(
            name="signal_generator",
            description="RF signal generator",
            noise_rms=0.0005,
            temp_coefficient=50e-6,
            settling_time=0.05,
            bandwidth_3db=1e9,
            linearity_error=0.005
        )

    @classmethod
    def power_supply(cls) -> "InstrumentProfile":
        """Profile for DC power supply."""
        return cls(
            name="power_supply",
            description="DC power supply",
            noise_rms=0.001,
            temp_coefficient=100e-6,
            settling_time=0.2,
            bandwidth_3db=1e3,
            linearity_error=0.01
        )