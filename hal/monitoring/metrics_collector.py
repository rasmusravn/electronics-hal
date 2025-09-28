"""
Metrics collection system for real-time monitoring.

This module provides comprehensive metrics collection for instruments,
tests, and system performance with real-time data streaming capabilities.
"""

import json
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from hal.logging_config import get_logger


class MetricPoint(BaseModel):
    """Single metric data point."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    name: str = Field(..., description="Metric name")
    value: Union[float, int, str, bool] = Field(..., description="Metric value")
    unit: Optional[str] = Field(default=None, description="Measurement unit")
    tags: Dict[str, str] = Field(default_factory=dict, description="Additional tags")
    source: str = Field(..., description="Data source identifier")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "tags": self.tags,
            "source": self.source
        }


class MetricsBuffer:
    """Thread-safe circular buffer for metrics storage."""

    def __init__(self, max_size: int = 10000):
        """Initialize metrics buffer."""
        self.max_size = max_size
        self._buffer = deque(maxlen=max_size)
        self._lock = threading.RLock()

    def add(self, metric: MetricPoint) -> None:
        """Add metric point to buffer."""
        with self._lock:
            self._buffer.append(metric)

    def get_recent(self, count: int = 100) -> List[MetricPoint]:
        """Get most recent metrics."""
        with self._lock:
            return list(self._buffer)[-count:]

    def get_by_name(self, name: str, count: int = 100) -> List[MetricPoint]:
        """Get recent metrics by name."""
        with self._lock:
            matching = [m for m in self._buffer if m.name == name]
            return matching[-count:]

    def get_by_source(self, source: str, count: int = 100) -> List[MetricPoint]:
        """Get recent metrics by source."""
        with self._lock:
            matching = [m for m in self._buffer if m.source == source]
            return matching[-count:]

    def get_time_range(self, start_time: datetime, end_time: datetime) -> List[MetricPoint]:
        """Get metrics within time range."""
        with self._lock:
            return [
                m for m in self._buffer
                if start_time <= m.timestamp <= end_time
            ]

    def clear(self) -> None:
        """Clear all metrics."""
        with self._lock:
            self._buffer.clear()

    def size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self._buffer)


class MetricsCollector:
    """Central metrics collection and management system."""

    def __init__(self, buffer_size: int = 10000, persistence_enabled: bool = True,
                 persistence_dir: Optional[Path] = None):
        """
        Initialize metrics collector.

        Args:
            buffer_size: Maximum number of metrics to keep in memory
            persistence_enabled: Enable metric persistence to disk
            persistence_dir: Directory for metric storage
        """
        self.buffer = MetricsBuffer(buffer_size)
        self.persistence_enabled = persistence_enabled
        self.persistence_dir = persistence_dir or Path("monitoring_data")
        self.logger = get_logger(__name__)

        # Create persistence directory
        if self.persistence_enabled:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)

        # Metric aggregations
        self._aggregations = defaultdict(list)
        self._aggregation_lock = threading.RLock()

        # Background persistence thread
        self._persistence_thread = None
        self._stop_persistence = threading.Event()

        if self.persistence_enabled:
            self._start_persistence_thread()

    def record_metric(self, name: str, value: Union[float, int, str, bool],
                     unit: Optional[str] = None, tags: Optional[Dict[str, str]] = None,
                     source: str = "system") -> None:
        """Record a single metric point."""
        metric = MetricPoint(
            name=name,
            value=value,
            unit=unit,
            tags=tags or {},
            source=source
        )

        self.buffer.add(metric)
        self._update_aggregations(metric)

        self.logger.debug(f"Recorded metric: {name}={value} from {source}")

    def record_instrument_metric(self, instrument_id: str, metric_name: str,
                                value: Union[float, int], unit: Optional[str] = None) -> None:
        """Record instrument-specific metric."""
        tags = {"instrument_id": instrument_id, "type": "instrument"}
        self.record_metric(
            name=f"instrument.{metric_name}",
            value=value,
            unit=unit,
            tags=tags,
            source=instrument_id
        )

    def record_test_metric(self, test_name: str, metric_name: str,
                          value: Union[float, int], unit: Optional[str] = None) -> None:
        """Record test execution metric."""
        tags = {"test_name": test_name, "type": "test"}
        self.record_metric(
            name=f"test.{metric_name}",
            value=value,
            unit=unit,
            tags=tags,
            source=test_name
        )

    def record_system_metric(self, metric_name: str, value: Union[float, int],
                            unit: Optional[str] = None) -> None:
        """Record system performance metric."""
        tags = {"type": "system"}
        self.record_metric(
            name=f"system.{metric_name}",
            value=value,
            unit=unit,
            tags=tags,
            source="system"
        )

    def get_metrics(self, name: Optional[str] = None, source: Optional[str] = None,
                   count: int = 100) -> List[MetricPoint]:
        """Get metrics with optional filtering."""
        if name:
            return self.buffer.get_by_name(name, count)
        elif source:
            return self.buffer.get_by_source(source, count)
        else:
            return self.buffer.get_recent(count)

    def get_metric_summary(self, name: str, duration_minutes: int = 60) -> Dict[str, Any]:
        """Get statistical summary of a metric over time period."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=duration_minutes)

        metrics = [
            m for m in self.buffer.get_by_name(name)
            if start_time <= m.timestamp <= end_time and isinstance(m.value, (int, float))
        ]

        if not metrics:
            return {"name": name, "count": 0, "error": "No numeric data found"}

        values = [float(m.value) for m in metrics]

        summary = {
            "name": name,
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "latest": values[-1] if values else None,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

        # Calculate standard deviation
        if len(values) > 1:
            mean = summary["mean"]
            variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
            summary["std_dev"] = variance ** 0.5

        return summary

    def get_instrument_status(self, instrument_id: str) -> Dict[str, Any]:
        """Get current status metrics for an instrument."""
        recent_metrics = self.buffer.get_by_source(instrument_id, 50)

        # Group by metric name
        by_name = defaultdict(list)
        for metric in recent_metrics:
            by_name[metric.name].append(metric)

        status = {
            "instrument_id": instrument_id,
            "last_activity": None,
            "metrics": {}
        }

        if recent_metrics:
            status["last_activity"] = max(m.timestamp for m in recent_metrics).isoformat()

        for name, metrics in by_name.items():
            latest = metrics[-1]
            status["metrics"][name] = {
                "value": latest.value,
                "unit": latest.unit,
                "timestamp": latest.timestamp.isoformat(),
                "count_last_hour": len([
                    m for m in metrics
                    if m.timestamp > datetime.utcnow() - timedelta(hours=1)
                ])
            }

        return status

    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health metrics."""
        recent_time = datetime.utcnow() - timedelta(minutes=5)
        recent_metrics = [
            m for m in self.buffer.get_recent(1000)
            if m.timestamp > recent_time
        ]

        # Count metrics by source
        sources = defaultdict(int)
        for metric in recent_metrics:
            sources[metric.source] += 1

        # Count metrics by type
        types = defaultdict(int)
        for metric in recent_metrics:
            metric_type = metric.tags.get("type", "unknown")
            types[metric_type] += 1

        health = {
            "total_metrics_5min": len(recent_metrics),
            "active_sources": len(sources),
            "buffer_utilization": self.buffer.size() / self.buffer.max_size,
            "metrics_by_source": dict(sources),
            "metrics_by_type": dict(types),
            "timestamp": datetime.utcnow().isoformat()
        }

        return health

    def _update_aggregations(self, metric: MetricPoint) -> None:
        """Update metric aggregations for performance."""
        with self._aggregation_lock:
            # Keep only recent values for performance
            key = f"{metric.source}.{metric.name}"
            self._aggregations[key].append(metric)

            # Limit aggregation history
            if len(self._aggregations[key]) > 1000:
                self._aggregations[key] = self._aggregations[key][-500:]

    def _start_persistence_thread(self) -> None:
        """Start background thread for metric persistence."""
        self._persistence_thread = threading.Thread(
            target=self._persistence_worker,
            daemon=True,
            name="MetricsPersistence"
        )
        self._persistence_thread.start()
        self.logger.info("Started metrics persistence thread")

    def _persistence_worker(self) -> None:
        """Background worker for persisting metrics to disk."""
        last_save = datetime.utcnow()
        save_interval = timedelta(minutes=5)

        while not self._stop_persistence.wait(30):  # Check every 30 seconds
            try:
                now = datetime.utcnow()
                if now - last_save >= save_interval:
                    self._save_metrics_to_disk()
                    last_save = now

            except Exception as e:
                self.logger.error(f"Error in metrics persistence: {e}")

    def _save_metrics_to_disk(self) -> None:
        """Save current metrics buffer to disk."""
        if not self.persistence_enabled:
            return

        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = self.persistence_dir / f"metrics_{timestamp}.json"

            # Get recent metrics
            metrics = self.buffer.get_recent(5000)
            if not metrics:
                return

            # Convert to JSON-serializable format
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "count": len(metrics),
                "metrics": [m.to_dict() for m in metrics]
            }

            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)

            self.logger.debug(f"Saved {len(metrics)} metrics to {filename}")

        except Exception as e:
            self.logger.error(f"Failed to save metrics to disk: {e}")

    def export_metrics(self, output_path: Path, format: str = "json",
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None) -> None:
        """Export metrics to file."""
        end_time = end_time or datetime.utcnow()
        start_time = start_time or (end_time - timedelta(hours=24))

        metrics = self.buffer.get_time_range(start_time, end_time)

        if format.lower() == "json":
            data = {
                "export_time": datetime.utcnow().isoformat(),
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "count": len(metrics),
                "metrics": [m.to_dict() for m in metrics]
            }

            with open(output_path, 'w') as f:
                json.dump(data, f, indent=2)

        elif format.lower() == "csv":
            import csv
            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "name", "value", "unit", "source", "tags"])

                for metric in metrics:
                    tags_str = json.dumps(metric.tags) if metric.tags else ""
                    writer.writerow([
                        metric.timestamp.isoformat(),
                        metric.name,
                        metric.value,
                        metric.unit or "",
                        metric.source,
                        tags_str
                    ])

        self.logger.info(f"Exported {len(metrics)} metrics to {output_path}")

    def stop(self) -> None:
        """Stop metrics collector and persistence."""
        if self._persistence_thread and self._persistence_thread.is_alive():
            self._stop_persistence.set()
            self._persistence_thread.join(timeout=5)

        if self.persistence_enabled:
            self._save_metrics_to_disk()

        self.logger.info("Metrics collector stopped")