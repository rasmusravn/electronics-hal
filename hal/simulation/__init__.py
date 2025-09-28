"""
Advanced Instrument Simulation Framework for Electronics HAL.

This module provides realistic instrument simulation with:
- Behavioral modeling with noise and drift
- Error injection for robustness testing
- Performance characteristics simulation
- State persistence and scenario recording
"""

from .simulator_engine import SimulatorEngine, SimulationConfig
from .behavioral_models import BehavioralModel, NoiseModel, DriftModel
from .error_injection import ErrorInjector, ErrorScenario
from .scenario_recorder import ScenarioRecorder, ScenarioPlayer
from .virtual_instruments import VirtualInstrumentFactory

__all__ = [
    "SimulatorEngine",
    "SimulationConfig",
    "BehavioralModel",
    "NoiseModel",
    "DriftModel",
    "ErrorInjector",
    "ErrorScenario",
    "ScenarioRecorder",
    "ScenarioPlayer",
    "VirtualInstrumentFactory"
]