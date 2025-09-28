#!/usr/bin/env python3
"""
Phase 3 Features Demonstration Script.

This script demonstrates the advanced Phase 3 capabilities including:
- Advanced instrument simulation
- Test scenario recording/playback
- Performance profiling and optimization
- Real-time monitoring

Usage:
    python examples/phase3_demo.py
"""

import time
from pathlib import Path

from hal.simulation.simulator_engine import SimulatorEngine, SimulationConfig
from hal.simulation.behavioral_models import InstrumentProfile
from hal.scenario.manager import ScenarioManager
from hal.performance.profiler import PerformanceProfiler
from hal.performance.cache_manager import CacheManager
from hal.monitoring.metrics_collector import MetricsCollector


def demo_advanced_simulation():
    """Demonstrate advanced instrument simulation capabilities."""
    print("\n" + "="*60)
    print("🎯 ADVANCED INSTRUMENT SIMULATION DEMO")
    print("="*60)

    # Create simulation engine with realistic behavior
    config = SimulationConfig(
        enable_noise=True,
        noise_level=0.002,
        enable_drift=True,
        drift_rate=0.0001,
        realistic_delays=True,
        warmup_time_seconds=5.0
    )

    engine = SimulatorEngine(config)

    # Simulate different instrument types with behavioral models
    instruments = {
        "precision_dmm": InstrumentProfile.precision_multimeter(),
        "benchtop_scope": InstrumentProfile.oscilloscope(),
        "signal_gen": InstrumentProfile.signal_generator()
    }

    print(f"📊 Created {len(instruments)} instrument profiles with realistic behavior")

    for name, profile in instruments.items():
        print(f"\n🔧 Testing {name}:")

        # Connect instrument
        success = engine.connect_instrument(name, profile.name)
        print(f"  Connection: {'✅ Success' if success else '❌ Failed'}")

        if success:
            # Simulate measurements with behavioral models
            behavioral_model = profile.create_behavioral_model()

            for i in range(3):
                base_value = 5.0
                context = {
                    "temperature": 23.0 + i,
                    "frequency": 1000.0,
                    "measurement_range": 10.0
                }

                # Apply behavioral model
                measured_value = behavioral_model.apply(base_value, context)
                print(f"  Measurement {i+1}: {measured_value:.6f} V (base: {base_value:.6f} V)")

            # Get instrument status
            status = engine.get_instrument_status(name)
            print(f"  Status: {status}")

            # Disconnect
            engine.disconnect_instrument(name)

    # Show overall simulation statistics
    stats = engine.get_simulation_statistics()
    print(f"\n📈 Simulation Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demo_scenario_recording_playback():
    """Demonstrate test scenario recording and playback."""
    print("\n" + "="*60)
    print("🎬 TEST SCENARIO RECORDING/PLAYBACK DEMO")
    print("="*60)

    scenario_dir = Path("demo_scenarios")
    scenario_dir.mkdir(exist_ok=True)

    manager = ScenarioManager(scenario_dir)

    # Record a test scenario
    print("🔴 Starting scenario recording...")
    scenario_id = manager.start_recording(
        "Demo Power Supply Test",
        "Demonstration of power supply voltage regulation testing"
    )

    print(f"📝 Recording scenario: {scenario_id}")

    # Simulate test steps (in real usage, these would be actual instrument operations)
    time.sleep(0.5)  # Simulate setup time

    # Simulate instrument connection
    print("  Recording: Instrument connection")

    # Simulate configuration
    print("  Recording: Setting output voltage to 5.0V")

    # Simulate measurements
    for i in range(3):
        print(f"  Recording: Measurement {i+1}")
        time.sleep(0.2)

    # Stop recording
    print("🛑 Stopping recording...")
    scenario = manager.stop_recording()

    if scenario:
        print(f"✅ Recorded scenario: {scenario.name}")
        print(f"   Steps: {len(scenario.steps)}")
        print(f"   Duration: {scenario.get_duration()}")

        # List available scenarios
        scenarios = manager.list_scenarios()
        print(f"\n📋 Available scenarios: {len(scenarios)}")

        # Demonstrate playback (dry run)
        print("\n▶️  Playing back scenario (dry run)...")
        result = manager.play_scenario(scenario_id, dry_run=True)

        print(f"✅ Playback completed:")
        print(f"   Success: {result.success}")
        print(f"   Steps executed: {result.steps_executed}")
        print(f"   Steps passed: {result.steps_passed}")

    else:
        print("❌ Failed to record scenario")


def demo_performance_profiling():
    """Demonstrate performance profiling and optimization."""
    print("\n" + "="*60)
    print("⚡ PERFORMANCE PROFILING & OPTIMIZATION DEMO")
    print("="*60)

    # Initialize profiler
    profiler = PerformanceProfiler(max_history=100)
    profiler.enable(True)

    print("📊 Performance profiler enabled")

    # Profile some operations
    @profiler.profile_function("demo_calculation")
    def expensive_calculation(n: int) -> float:
        """Simulate expensive calculation."""
        result = 0.0
        for i in range(n):
            result += i ** 0.5
        return result

    @profiler.profile_function("demo_io_operation")
    def simulate_io_operation():
        """Simulate I/O operation."""
        time.sleep(0.1)  # Simulate network/disk delay
        return "Data retrieved"

    # Execute profiled operations
    print("\n🔧 Executing profiled operations...")

    for i in range(5):
        # Vary the calculation complexity
        complexity = 1000 * (i + 1)
        result = expensive_calculation(complexity)
        print(f"  Calculation {i+1}: {result:.2f} (complexity: {complexity})")

        # Simulate I/O
        data = simulate_io_operation()
        print(f"  I/O operation {i+1}: {data}")

    # Get profiling results
    print("\n📈 Profiling Results:")
    stats = profiler.get_all_operation_stats()

    for stat in stats:
        print(f"\n🎯 Operation: {stat['operation_name']}")
        print(f"   Call count: {stat['call_count']}")
        print(f"   Average duration: {stat['duration_stats']['avg']:.4f}s")
        print(f"   Total time: {stat['duration_stats']['total']:.4f}s")
        print(f"   Throughput: {stat['throughput_ops_per_sec']:.2f} ops/sec")

    # Demonstrate caching
    print("\n💾 Cache Manager Demo:")
    cache_dir = Path("demo_cache")
    cache_manager = CacheManager(
        memory_cache_size=100,
        persistent_cache_dir=cache_dir,
        persistent_cache_size_mb=10.0
    )

    # Cache some data
    cache_manager.cache_instrument_config("dmm_001", {
        "range": "10V",
        "resolution": "6.5_digit",
        "integration_time": "medium"
    })

    cache_manager.cache_measurement("dmm_001", "dc_voltage",
                                   {"range": "10V"}, 5.123456)

    # Retrieve cached data
    config = cache_manager.get_instrument_config("dmm_001")
    measurement = cache_manager.get_cached_measurement("dmm_001", "dc_voltage", {"range": "10V"})

    print(f"   Cached config: {config}")
    print(f"   Cached measurement: {measurement}")

    # Get cache statistics
    cache_stats = cache_manager.get_stats()
    print(f"   Memory cache hit rate: {cache_stats['memory_cache']['hit_rate_percent']:.1f}%")


def demo_real_time_monitoring():
    """Demonstrate real-time monitoring capabilities."""
    print("\n" + "="*60)
    print("📡 REAL-TIME MONITORING DEMO")
    print("="*60)

    # Initialize metrics collector
    metrics = MetricsCollector(buffer_size=1000, persistence_enabled=False)

    print("📊 Metrics collector initialized")

    # Simulate real-time data collection
    print("\n📈 Simulating real-time metrics...")

    for i in range(10):
        # Instrument metrics
        metrics.record_instrument_metric("power_supply_1", "output_voltage", 5.0 + i * 0.01)
        metrics.record_instrument_metric("power_supply_1", "output_current", 2.0 + i * 0.005)

        # Test metrics
        metrics.record_test_metric("voltage_regulation_test", "duration_ms", 100 + i * 10)
        metrics.record_test_metric("voltage_regulation_test", "success_rate", 95.0 + i * 0.5)

        # System metrics
        metrics.record_system_metric("cpu_usage", 45.0 + i * 2)
        metrics.record_system_metric("memory_usage", 60.0 + i * 1)

        time.sleep(0.1)  # Simulate real-time interval

    print(f"✅ Recorded metrics in buffer (size: {metrics.buffer.size()})")

    # Get instrument status
    status = metrics.get_instrument_status("power_supply_1")
    print(f"\n🔧 Instrument Status:")
    for key, value in status.items():
        if key != "metrics":
            print(f"   {key}: {value}")

    # Get system health
    health = metrics.get_system_health()
    print(f"\n💚 System Health:")
    print(f"   Active sources: {health['active_sources']}")
    print(f"   Buffer utilization: {health['buffer_utilization']:.1%}")
    print(f"   Metrics in last 5min: {health['total_metrics_5min']}")

    # Get metric summary
    summary = metrics.get_metric_summary("instrument.output_voltage", duration_minutes=1)
    if summary.get("count", 0) > 0:
        print(f"\n📊 Voltage Metric Summary (last minute):")
        print(f"   Count: {summary['count']}")
        print(f"   Average: {summary['mean']:.3f}V")
        print(f"   Range: {summary['min']:.3f}V - {summary['max']:.3f}V")


def main():
    """Run Phase 3 features demonstration."""
    print("🚀 Electronics HAL - Phase 3 Features Demonstration")
    print("This demo showcases advanced enterprise capabilities")

    try:
        # Run all demonstrations
        demo_advanced_simulation()
        demo_scenario_recording_playbook()
        demo_performance_profiling()
        demo_real_time_monitoring()

        print("\n" + "="*60)
        print("🎉 PHASE 3 DEMONSTRATION COMPLETE!")
        print("="*60)
        print("\n✅ Successfully demonstrated:")
        print("   • Advanced instrument simulation with behavioral models")
        print("   • Test scenario recording and playback system")
        print("   • Performance profiling and optimization")
        print("   • Real-time monitoring and metrics collection")
        print("\n🚀 Electronics HAL is ready for enterprise deployment!")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()