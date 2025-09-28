"""
Core simulation engine for realistic instrument behavior.

This module provides the foundation for advanced instrument simulation
including behavioral modeling, performance characteristics, and state management.
"""

import json
import random
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from hal.logging_config import get_logger


class SimulationConfig(BaseModel):
    """Configuration for instrument simulation behavior."""

    # Behavioral Parameters
    enable_noise: bool = Field(default=True, description="Enable measurement noise")
    noise_level: float = Field(default=0.001, description="Relative noise level (0.0-1.0)")

    enable_drift: bool = Field(default=True, description="Enable measurement drift")
    drift_rate: float = Field(default=0.0001, description="Drift rate per second")

    # Timing Parameters
    realistic_delays: bool = Field(default=True, description="Simulate realistic command delays")
    base_command_delay_ms: float = Field(default=10.0, description="Base command processing delay")
    measurement_delay_ms: float = Field(default=50.0, description="Measurement acquisition delay")

    # Error Injection
    enable_errors: bool = Field(default=False, description="Enable random error injection")
    error_probability: float = Field(default=0.001, description="Probability of error per operation")

    # Performance
    warmup_time_seconds: float = Field(default=30.0, description="Instrument warmup time")
    calibration_drift_hours: float = Field(default=24.0, description="Hours between calibration drift")

    # Storage
    state_persistence: bool = Field(default=True, description="Persist instrument state")
    simulation_data_dir: Path = Field(default=Path("simulation_data"), description="Simulation data directory")

    def __post_init__(self):
        """Create simulation data directory."""
        if self.state_persistence:
            self.simulation_data_dir.mkdir(parents=True, exist_ok=True)


class InstrumentState(BaseModel):
    """Persistent instrument state for realistic simulation."""

    instrument_id: str = Field(..., description="Unique instrument identifier")
    instrument_type: str = Field(..., description="Instrument type")

    # Power and Connection State
    is_powered: bool = Field(default=False, description="Power state")
    is_connected: bool = Field(default=False, description="Connection state")
    connection_time: Optional[datetime] = Field(default=None, description="Connection timestamp")

    # Operational State
    is_warmed_up: bool = Field(default=False, description="Warmup state")
    warmup_start_time: Optional[datetime] = Field(default=None, description="Warmup start time")
    last_calibration: Optional[datetime] = Field(default=None, description="Last calibration time")

    # Configuration State
    configuration: Dict[str, Any] = Field(default_factory=dict, description="Instrument configuration")

    # Performance State
    operation_count: int = Field(default=0, description="Total operations performed")
    error_count: int = Field(default=0, description="Total errors encountered")
    last_operation_time: Optional[datetime] = Field(default=None, description="Last operation timestamp")

    # Behavioral State
    drift_accumulation: float = Field(default=0.0, description="Accumulated measurement drift")
    temperature_drift: float = Field(default=0.0, description="Temperature-induced drift")

    def update_operation_stats(self, success: bool = True) -> None:
        """Update operation statistics."""
        self.operation_count += 1
        self.last_operation_time = datetime.utcnow()
        if not success:
            self.error_count += 1

    def get_reliability_factor(self) -> float:
        """Calculate reliability factor based on usage."""
        if self.operation_count == 0:
            return 1.0

        error_rate = self.error_count / self.operation_count
        return max(0.5, 1.0 - error_rate * 10)  # Don't go below 50% reliability

    def needs_calibration(self, drift_hours: float = 24.0) -> bool:
        """Check if instrument needs calibration."""
        if self.last_calibration is None:
            return True

        time_since_cal = datetime.utcnow() - self.last_calibration
        return time_since_cal > timedelta(hours=drift_hours)

    def perform_calibration(self) -> None:
        """Perform instrument calibration."""
        self.last_calibration = datetime.utcnow()
        self.drift_accumulation = 0.0
        self.temperature_drift = 0.0


class SimulatorEngine:
    """Advanced simulation engine for realistic instrument behavior."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self._states: Dict[str, InstrumentState] = {}
        self._random = random.Random()
        self._random.seed(42)  # Reproducible behavior

        # Load persisted states if enabled
        if config.state_persistence:
            self._load_states()

    def get_instrument_state(self, instrument_id: str, instrument_type: str) -> InstrumentState:
        """Get or create instrument state."""
        if instrument_id not in self._states:
            self._states[instrument_id] = InstrumentState(
                instrument_id=instrument_id,
                instrument_type=instrument_type
            )
            self.logger.debug(f"Created new state for {instrument_type} {instrument_id}")

        return self._states[instrument_id]

    def connect_instrument(self, instrument_id: str, instrument_type: str) -> bool:
        """Simulate instrument connection with realistic behavior."""
        state = self.get_instrument_state(instrument_id, instrument_type)

        # Simulate connection delay
        if self.config.realistic_delays:
            delay = self.config.base_command_delay_ms / 1000.0
            delay += self._random.uniform(0, delay)  # Add jitter
            time.sleep(delay)

        # Simulate connection failures occasionally
        if self.config.enable_errors and self._random.random() < self.config.error_probability * 10:
            self.logger.warning(f"Simulated connection failure for {instrument_id}")
            state.update_operation_stats(success=False)
            return False

        state.is_connected = True
        state.is_powered = True
        state.connection_time = datetime.utcnow()
        state.warmup_start_time = datetime.utcnow()
        state.update_operation_stats(success=True)

        self.logger.info(f"Connected to simulated {instrument_type} {instrument_id}")
        self._save_state(instrument_id)
        return True

    def disconnect_instrument(self, instrument_id: str) -> None:
        """Simulate instrument disconnection."""
        if instrument_id in self._states:
            state = self._states[instrument_id]
            state.is_connected = False
            state.is_powered = False
            state.is_warmed_up = False
            state.connection_time = None
            state.warmup_start_time = None
            state.update_operation_stats(success=True)

            self.logger.info(f"Disconnected from simulated instrument {instrument_id}")
            self._save_state(instrument_id)

    def is_warmed_up(self, instrument_id: str) -> bool:
        """Check if instrument is warmed up."""
        if instrument_id not in self._states:
            return False

        state = self._states[instrument_id]
        if not state.is_connected or state.warmup_start_time is None:
            return False

        elapsed = datetime.utcnow() - state.warmup_start_time
        is_warmed = elapsed.total_seconds() >= self.config.warmup_time_seconds

        if is_warmed and not state.is_warmed_up:
            state.is_warmed_up = True
            self.logger.info(f"Instrument {instrument_id} warmup complete")
            self._save_state(instrument_id)

        return is_warmed

    def simulate_measurement(self, instrument_id: str, base_value: float,
                           measurement_type: str = "generic") -> float:
        """Simulate realistic measurement with noise, drift, and errors."""
        state = self.get_instrument_state(instrument_id, "unknown")

        # Check connection
        if not state.is_connected:
            raise RuntimeError(f"Instrument {instrument_id} not connected")

        # Simulate measurement delay
        if self.config.realistic_delays:
            delay = self.config.measurement_delay_ms / 1000.0
            time.sleep(delay)

        # Simulate random errors
        if self.config.enable_errors and self._random.random() < self.config.error_probability:
            state.update_operation_stats(success=False)
            raise RuntimeError(f"Simulated measurement error in {measurement_type}")

        # Start with base value
        value = base_value

        # Add noise if enabled
        if self.config.enable_noise:
            noise_amplitude = abs(base_value) * self.config.noise_level
            noise = self._random.gauss(0, noise_amplitude)
            value += noise

        # Add drift if enabled
        if self.config.enable_drift:
            # Accumulate drift over time
            if state.last_operation_time:
                time_delta = datetime.utcnow() - state.last_operation_time
                drift_increment = self.config.drift_rate * time_delta.total_seconds()
                state.drift_accumulation += drift_increment

            # Apply drift
            value += base_value * state.drift_accumulation

        # Apply warmup effects
        if not self.is_warmed_up(instrument_id):
            warmup_factor = 0.95  # 5% accuracy reduction when cold
            value *= warmup_factor

        # Apply calibration drift
        if state.needs_calibration(self.config.calibration_drift_hours):
            cal_drift = self._random.uniform(-0.002, 0.002)  # ±0.2% drift
            value *= (1 + cal_drift)

        state.update_operation_stats(success=True)
        self._save_state(instrument_id)

        return value

    def simulate_command_execution(self, instrument_id: str, command: str,
                                 success_probability: float = 0.99) -> bool:
        """Simulate command execution with realistic timing and errors."""
        state = self.get_instrument_state(instrument_id, "unknown")

        # Check connection
        if not state.is_connected:
            raise RuntimeError(f"Instrument {instrument_id} not connected")

        # Simulate command delay
        if self.config.realistic_delays:
            delay = self.config.base_command_delay_ms / 1000.0
            time.sleep(delay)

        # Simulate command failures
        if self.config.enable_errors:
            failure_prob = self.config.error_probability + (1 - success_probability)
            if self._random.random() < failure_prob:
                state.update_operation_stats(success=False)
                self.logger.warning(f"Simulated command failure: {command}")
                return False

        state.update_operation_stats(success=True)
        self._save_state(instrument_id)
        return True

    def get_instrument_status(self, instrument_id: str) -> Dict[str, Any]:
        """Get comprehensive instrument status."""
        if instrument_id not in self._states:
            return {"connected": False, "error": "Instrument not found"}

        state = self._states[instrument_id]

        status = {
            "connected": state.is_connected,
            "powered": state.is_powered,
            "warmed_up": self.is_warmed_up(instrument_id),
            "needs_calibration": state.needs_calibration(self.config.calibration_drift_hours),
            "operation_count": state.operation_count,
            "error_count": state.error_count,
            "reliability_factor": state.get_reliability_factor(),
            "drift_accumulation": state.drift_accumulation
        }

        if state.connection_time:
            uptime = datetime.utcnow() - state.connection_time
            status["uptime_seconds"] = uptime.total_seconds()

        return status

    def reset_instrument_state(self, instrument_id: str) -> None:
        """Reset instrument to factory defaults."""
        if instrument_id in self._states:
            state = self._states[instrument_id]
            state.drift_accumulation = 0.0
            state.temperature_drift = 0.0
            state.operation_count = 0
            state.error_count = 0
            state.perform_calibration()
            self.logger.info(f"Reset state for instrument {instrument_id}")
            self._save_state(instrument_id)

    def _save_state(self, instrument_id: str) -> None:
        """Save instrument state to disk."""
        if not self.config.state_persistence or instrument_id not in self._states:
            return

        state_file = self.config.simulation_data_dir / f"{instrument_id}_state.json"
        try:
            with open(state_file, 'w') as f:
                json.dump(self._states[instrument_id].dict(), f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Failed to save state for {instrument_id}: {e}")

    def _load_states(self) -> None:
        """Load persisted instrument states."""
        if not self.config.simulation_data_dir.exists():
            return

        for state_file in self.config.simulation_data_dir.glob("*_state.json"):
            try:
                with open(state_file, 'r') as f:
                    state_data = json.load(f)

                instrument_id = state_data["instrument_id"]
                self._states[instrument_id] = InstrumentState(**state_data)
                self.logger.debug(f"Loaded state for {instrument_id}")

            except Exception as e:
                self.logger.error(f"Failed to load state from {state_file}: {e}")

    def get_simulation_statistics(self) -> Dict[str, Any]:
        """Get overall simulation statistics."""
        if not self._states:
            return {"total_instruments": 0}

        total_ops = sum(state.operation_count for state in self._states.values())
        total_errors = sum(state.error_count for state in self._states.values())

        stats = {
            "total_instruments": len(self._states),
            "connected_instruments": sum(1 for state in self._states.values() if state.is_connected),
            "total_operations": total_ops,
            "total_errors": total_errors,
            "overall_reliability": (total_ops - total_errors) / max(1, total_ops),
            "instruments_needing_calibration": sum(
                1 for state in self._states.values()
                if state.needs_calibration(self.config.calibration_drift_hours)
            )
        }

        return stats