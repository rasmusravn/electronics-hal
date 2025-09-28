"""
Performance Metrics and Optimization System for Electronics HAL.

This module provides comprehensive performance monitoring, analysis,
and optimization capabilities for instrument operations and test execution.
"""

from .profiler import PerformanceProfiler, ProfileSession
from .metrics import PerformanceMetrics, MetricCollector
from .optimizer import PerformanceOptimizer, OptimizationSuggestion
from .cache_manager import CacheManager, CacheStrategy
from .benchmarks import BenchmarkRunner, BenchmarkSuite

__all__ = [
    "PerformanceProfiler",
    "ProfileSession",
    "PerformanceMetrics",
    "MetricCollector",
    "PerformanceOptimizer",
    "OptimizationSuggestion",
    "CacheManager",
    "CacheStrategy",
    "BenchmarkRunner",
    "BenchmarkSuite"
]