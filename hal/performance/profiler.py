"""
Performance profiling system for Electronics HAL.

This module provides detailed performance profiling capabilities for
instrument operations, test execution, and system resource usage.
"""

import functools
import psutil
import time
import threading
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from pydantic import BaseModel, Field

from hal.logging_config import get_logger


class ProfileMetrics(BaseModel):
    """Performance metrics for a profiled operation."""

    operation_name: str = Field(..., description="Name of the profiled operation")
    start_time: datetime = Field(..., description="Operation start time")
    end_time: datetime = Field(..., description="Operation end time")
    duration_seconds: float = Field(..., description="Execution duration in seconds")
    cpu_percent_avg: float = Field(default=0.0, description="Average CPU usage during operation")
    memory_peak_mb: float = Field(default=0.0, description="Peak memory usage in MB")
    memory_delta_mb: float = Field(default=0.0, description="Memory change during operation")
    thread_id: int = Field(..., description="Thread ID where operation executed")
    call_count: int = Field(default=1, description="Number of times operation was called")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_throughput(self) -> float:
        """Calculate operations per second."""
        if self.duration_seconds > 0:
            return self.call_count / self.duration_seconds
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "operation_name": self.operation_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "throughput_ops_per_sec": self.get_throughput(),
            "cpu_percent_avg": self.cpu_percent_avg,
            "memory_peak_mb": self.memory_peak_mb,
            "memory_delta_mb": self.memory_delta_mb,
            "thread_id": self.thread_id,
            "call_count": self.call_count,
            "metadata": self.metadata
        }


class ProfileSession:
    """Individual profiling session with resource monitoring."""

    def __init__(self, operation_name: str, monitor_resources: bool = True):
        """Initialize profile session."""
        self.operation_name = operation_name
        self.monitor_resources = monitor_resources
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # Resource monitoring
        self.process = psutil.Process()
        self.initial_memory = 0.0
        self.peak_memory = 0.0
        self.cpu_samples: List[float] = []
        self.monitoring_active = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_monitoring = threading.Event()

        self.metadata: Dict[str, Any] = {}

    def start(self) -> None:
        """Start profiling session."""
        self.start_time = datetime.utcnow()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        if self.monitor_resources:
            self._start_resource_monitoring()

    def stop(self) -> ProfileMetrics:
        """Stop profiling and return metrics."""
        self.end_time = datetime.utcnow()

        if self.monitor_resources:
            self._stop_resource_monitoring()

        if not self.start_time:
            raise RuntimeError("Profile session was not started")

        duration = (self.end_time - self.start_time).total_seconds()
        current_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        return ProfileMetrics(
            operation_name=self.operation_name,
            start_time=self.start_time,
            end_time=self.end_time,
            duration_seconds=duration,
            cpu_percent_avg=sum(self.cpu_samples) / len(self.cpu_samples) if self.cpu_samples else 0.0,
            memory_peak_mb=self.peak_memory,
            memory_delta_mb=current_memory - self.initial_memory,
            thread_id=threading.get_ident(),
            metadata=self.metadata
        )

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the session."""
        self.metadata[key] = value

    def _start_resource_monitoring(self) -> None:
        """Start background resource monitoring."""
        self.monitoring_active = True
        self.stop_monitoring.clear()
        self.monitor_thread = threading.Thread(target=self._monitor_resources, daemon=True)
        self.monitor_thread.start()

    def _stop_resource_monitoring(self) -> None:
        """Stop background resource monitoring."""
        self.monitoring_active = False
        self.stop_monitoring.set()

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def _monitor_resources(self) -> None:
        """Background resource monitoring worker."""
        while self.monitoring_active and not self.stop_monitoring.wait(0.1):
            try:
                # Sample CPU usage
                cpu_percent = self.process.cpu_percent()
                if cpu_percent > 0:  # Filter out initial zero readings
                    self.cpu_samples.append(cpu_percent)

                # Track peak memory
                memory_mb = self.process.memory_info().rss / 1024 / 1024
                self.peak_memory = max(self.peak_memory, memory_mb)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Process might have ended or access denied
                break
            except Exception:
                # Ignore other monitoring errors
                pass


class PerformanceProfiler:
    """Comprehensive performance profiler for Electronics HAL operations."""

    def __init__(self, max_history: int = 1000):
        """Initialize performance profiler."""
        self.max_history = max_history
        self.logger = get_logger(__name__)

        # Store profiling results
        self.profiles: deque = deque(maxlen=max_history)
        self.operation_stats: Dict[str, List[ProfileMetrics]] = defaultdict(list)

        # Configuration
        self.enabled = True
        self.monitor_resources = True
        self.min_duration_threshold = 0.001  # Only profile operations > 1ms

        self.logger.info("Performance profiler initialized")

    def enable(self, enabled: bool = True) -> None:
        """Enable or disable profiling."""
        self.enabled = enabled
        self.logger.info(f"Performance profiling {'enabled' if enabled else 'disabled'}")

    def set_resource_monitoring(self, enabled: bool = True) -> None:
        """Enable or disable resource monitoring."""
        self.monitor_resources = enabled

    def set_duration_threshold(self, threshold_seconds: float) -> None:
        """Set minimum duration threshold for profiling."""
        self.min_duration_threshold = threshold_seconds

    @contextmanager
    def profile_operation(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None):
        """Context manager for profiling operations."""
        if not self.enabled:
            yield
            return

        session = ProfileSession(operation_name, self.monitor_resources)

        if metadata:
            for key, value in metadata.items():
                session.add_metadata(key, value)

        session.start()

        try:
            yield session
        finally:
            metrics = session.stop()

            # Only store if above threshold
            if metrics.duration_seconds >= self.min_duration_threshold:
                self._store_metrics(metrics)

    def profile_function(self, operation_name: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None):
        """Decorator for profiling functions."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                name = operation_name or f"{func.__module__}.{func.__name__}"

                with self.profile_operation(name, metadata) as session:
                    if session:
                        session.add_metadata("function", func.__name__)
                        session.add_metadata("module", func.__module__)
                        session.add_metadata("args_count", len(args))
                        session.add_metadata("kwargs_count", len(kwargs))

                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def profile_instrument_operation(self, instrument_id: str, operation: str):
        """Decorator for profiling instrument operations."""
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                name = f"instrument.{operation}"
                metadata = {
                    "instrument_id": instrument_id,
                    "operation": operation,
                    "function": func.__name__
                }

                with self.profile_operation(name, metadata):
                    return func(*args, **kwargs)

            return wrapper
        return decorator

    def _store_metrics(self, metrics: ProfileMetrics) -> None:
        """Store profiling metrics."""
        self.profiles.append(metrics)
        self.operation_stats[metrics.operation_name].append(metrics)

        # Limit per-operation history
        if len(self.operation_stats[metrics.operation_name]) > 100:
            self.operation_stats[metrics.operation_name] = \
                self.operation_stats[metrics.operation_name][-50:]

        self.logger.debug(f"Stored profile: {metrics.operation_name} ({metrics.duration_seconds:.3f}s)")

    def get_operation_stats(self, operation_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific operation."""
        if operation_name not in self.operation_stats:
            return None

        metrics_list = self.operation_stats[operation_name]
        if not metrics_list:
            return None

        durations = [m.duration_seconds for m in metrics_list]
        cpu_usages = [m.cpu_percent_avg for m in metrics_list]
        memory_deltas = [m.memory_delta_mb for m in metrics_list]

        return {
            "operation_name": operation_name,
            "call_count": len(metrics_list),
            "duration_stats": {
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "total": sum(durations)
            },
            "cpu_stats": {
                "min": min(cpu_usages) if cpu_usages else 0,
                "max": max(cpu_usages) if cpu_usages else 0,
                "avg": sum(cpu_usages) / len(cpu_usages) if cpu_usages else 0
            },
            "memory_stats": {
                "min_delta": min(memory_deltas) if memory_deltas else 0,
                "max_delta": max(memory_deltas) if memory_deltas else 0,
                "avg_delta": sum(memory_deltas) / len(memory_deltas) if memory_deltas else 0
            },
            "throughput_ops_per_sec": len(metrics_list) / sum(durations) if sum(durations) > 0 else 0,
            "last_execution": metrics_list[-1].end_time.isoformat()
        }

    def get_all_operation_stats(self) -> List[Dict[str, Any]]:
        """Get statistics for all operations."""
        stats = []
        for operation_name in self.operation_stats:
            stat = self.get_operation_stats(operation_name)
            if stat:
                stats.append(stat)

        # Sort by total duration (most expensive operations first)
        stats.sort(key=lambda x: x["duration_stats"]["total"], reverse=True)
        return stats

    def get_recent_profiles(self, count: int = 50) -> List[Dict[str, Any]]:
        """Get recent profile results."""
        recent = list(self.profiles)[-count:]
        return [profile.to_dict() for profile in recent]

    def get_slow_operations(self, threshold_seconds: float = 1.0) -> List[Dict[str, Any]]:
        """Get operations that exceed duration threshold."""
        slow_ops = []

        for metrics in self.profiles:
            if metrics.duration_seconds >= threshold_seconds:
                slow_ops.append(metrics.to_dict())

        # Sort by duration (slowest first)
        slow_ops.sort(key=lambda x: x["duration_seconds"], reverse=True)
        return slow_ops

    def get_memory_intensive_operations(self, threshold_mb: float = 10.0) -> List[Dict[str, Any]]:
        """Get operations with high memory usage."""
        memory_ops = []

        for metrics in self.profiles:
            if abs(metrics.memory_delta_mb) >= threshold_mb:
                memory_ops.append(metrics.to_dict())

        # Sort by memory delta (highest first)
        memory_ops.sort(key=lambda x: abs(x["memory_delta_mb"]), reverse=True)
        return memory_ops

    def analyze_performance_trends(self, operation_name: str,
                                 window_size: int = 20) -> Dict[str, Any]:
        """Analyze performance trends for an operation."""
        if operation_name not in self.operation_stats:
            return {"error": f"No data for operation: {operation_name}"}

        metrics_list = self.operation_stats[operation_name]
        if len(metrics_list) < window_size:
            return {"error": f"Insufficient data (need {window_size}, have {len(metrics_list)})"}

        # Get recent and older windows
        recent_window = metrics_list[-window_size:]
        older_window = metrics_list[-2*window_size:-window_size] if len(metrics_list) >= 2*window_size else []

        recent_avg_duration = sum(m.duration_seconds for m in recent_window) / len(recent_window)

        analysis = {
            "operation_name": operation_name,
            "recent_avg_duration": recent_avg_duration,
            "trend": "stable"
        }

        if older_window:
            older_avg_duration = sum(m.duration_seconds for m in older_window) / len(older_window)
            analysis["older_avg_duration"] = older_avg_duration

            # Calculate trend
            change_percent = ((recent_avg_duration - older_avg_duration) / older_avg_duration) * 100

            if change_percent > 10:
                analysis["trend"] = "degrading"
            elif change_percent < -10:
                analysis["trend"] = "improving"

            analysis["change_percent"] = change_percent

        return analysis

    def export_profile_data(self, output_path: Path, format: str = "json") -> None:
        """Export profile data to file."""
        data = {
            "export_time": datetime.utcnow().isoformat(),
            "total_profiles": len(self.profiles),
            "operation_stats": self.get_all_operation_stats(),
            "recent_profiles": [p.to_dict() for p in self.profiles]
        }

        if format.lower() == "json":
            import json
            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)

        elif format.lower() == "csv":
            import csv
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "operation_name", "start_time", "duration_seconds", "cpu_percent_avg",
                    "memory_peak_mb", "memory_delta_mb", "thread_id"
                ])

                for profile in self.profiles:
                    writer.writerow([
                        profile.operation_name,
                        profile.start_time.isoformat(),
                        profile.duration_seconds,
                        profile.cpu_percent_avg,
                        profile.memory_peak_mb,
                        profile.memory_delta_mb,
                        profile.thread_id
                    ])

        self.logger.info(f"Exported {len(self.profiles)} profiles to {output_path}")

    def clear_profiles(self) -> None:
        """Clear all stored profiles."""
        self.profiles.clear()
        self.operation_stats.clear()
        self.logger.info("Cleared all profile data")

    def get_summary(self) -> Dict[str, Any]:
        """Get profiler summary statistics."""
        if not self.profiles:
            return {
                "enabled": self.enabled,
                "total_profiles": 0,
                "operations_tracked": 0
            }

        total_duration = sum(p.duration_seconds for p in self.profiles)
        avg_duration = total_duration / len(self.profiles)

        return {
            "enabled": self.enabled,
            "resource_monitoring": self.monitor_resources,
            "duration_threshold": self.min_duration_threshold,
            "total_profiles": len(self.profiles),
            "operations_tracked": len(self.operation_stats),
            "total_execution_time": total_duration,
            "avg_execution_time": avg_duration,
            "slowest_operation": max(self.profiles, key=lambda x: x.duration_seconds).operation_name,
            "most_frequent_operation": max(self.operation_stats.items(), key=lambda x: len(x[1]))[0]
        }