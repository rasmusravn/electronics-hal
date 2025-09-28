"""
Intelligent caching system for Electronics HAL performance optimization.

This module provides sophisticated caching strategies for instrument data,
configuration settings, and measurement results to improve performance.
"""

import hashlib
import pickle
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from pydantic import BaseModel, Field

from hal.logging_config import get_logger


class CacheStrategy(str, Enum):
    """Cache eviction strategies."""

    LRU = "lru"  # Least Recently Used
    LFU = "lfu"  # Least Frequently Used
    TTL = "ttl"  # Time To Live
    FIFO = "fifo"  # First In, First Out


class CacheEntry(BaseModel):
    """Cache entry with metadata."""

    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cached value")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Entry creation time")
    accessed_at: datetime = Field(default_factory=datetime.utcnow, description="Last access time")
    access_count: int = Field(default=0, description="Number of times accessed")
    ttl_seconds: Optional[float] = Field(default=None, description="Time to live in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl_seconds is None:
            return False

        age = (datetime.utcnow() - self.created_at).total_seconds()
        return age > self.ttl_seconds

    def touch(self) -> None:
        """Update access time and count."""
        self.accessed_at = datetime.utcnow()
        self.access_count += 1

    def get_age_seconds(self) -> float:
        """Get entry age in seconds."""
        return (datetime.utcnow() - self.created_at).total_seconds()


class Cache(ABC):
    """Abstract base class for cache implementations."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        pass


class MemoryCache(Cache):
    """In-memory cache with configurable eviction strategies."""

    def __init__(self, max_size: int = 1000, strategy: CacheStrategy = CacheStrategy.LRU):
        """Initialize memory cache."""
        self.max_size = max_size
        self.strategy = strategy
        self.logger = get_logger(__name__)

        self._entries: Dict[str, CacheEntry] = {}
        self._access_order: OrderedDict = OrderedDict()  # For LRU

        # Statistics
        self.hit_count = 0
        self.miss_count = 0
        self.eviction_count = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        entry = self._entries.get(key)

        if entry is None:
            self.miss_count += 1
            return None

        # Check expiration
        if entry.is_expired():
            self.delete(key)
            self.miss_count += 1
            return None

        # Update access information
        entry.touch()

        # Update access order for LRU
        if self.strategy == CacheStrategy.LRU:
            self._access_order.move_to_end(key)

        self.hit_count += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in cache."""
        # Remove existing entry if present
        if key in self._entries:
            self.delete(key)

        # Check if we need to evict
        if len(self._entries) >= self.max_size:
            self._evict()

        # Create new entry
        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl
        )

        self._entries[key] = entry

        # Update access order for LRU
        if self.strategy == CacheStrategy.LRU:
            self._access_order[key] = True

        self.logger.debug(f"Cached key: {key} (TTL: {ttl})")

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        if key in self._entries:
            del self._entries[key]
            self._access_order.pop(key, None)
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._entries)
        self._entries.clear()
        self._access_order.clear()
        self.logger.info(f"Cleared {count} cache entries")

    def _evict(self) -> None:
        """Evict entries based on strategy."""
        if not self._entries:
            return

        if self.strategy == CacheStrategy.LRU:
            # Remove least recently used
            key_to_remove = next(iter(self._access_order))

        elif self.strategy == CacheStrategy.LFU:
            # Remove least frequently used
            key_to_remove = min(self._entries.keys(),
                               key=lambda k: self._entries[k].access_count)

        elif self.strategy == CacheStrategy.TTL:
            # Remove expired entries first, then oldest
            expired_keys = [k for k, e in self._entries.items() if e.is_expired()]
            if expired_keys:
                key_to_remove = expired_keys[0]
            else:
                key_to_remove = min(self._entries.keys(),
                                   key=lambda k: self._entries[k].created_at)

        elif self.strategy == CacheStrategy.FIFO:
            # Remove oldest entry
            key_to_remove = min(self._entries.keys(),
                               key=lambda k: self._entries[k].created_at)

        else:
            # Default to LRU
            key_to_remove = next(iter(self._access_order))

        self.delete(key_to_remove)
        self.eviction_count += 1
        self.logger.debug(f"Evicted key: {key_to_remove}")

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        expired_keys = [k for k, e in self._entries.items() if e.is_expired()]

        for key in expired_keys:
            self.delete(key)

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired entries")

        return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0

        return {
            "strategy": self.strategy.value,
            "max_size": self.max_size,
            "current_size": len(self._entries),
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate_percent": hit_rate,
            "eviction_count": self.eviction_count,
            "expired_entries": sum(1 for e in self._entries.values() if e.is_expired())
        }


class PersistentCache(Cache):
    """Disk-based persistent cache."""

    def __init__(self, cache_dir: Path, max_size_mb: float = 100.0):
        """Initialize persistent cache."""
        self.cache_dir = cache_dir
        self.max_size_mb = max_size_mb
        self.logger = get_logger(__name__)

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Statistics
        self.hit_count = 0
        self.miss_count = 0

    def _get_file_path(self, key: str) -> Path:
        """Get file path for cache key."""
        # Hash the key to create safe filename
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    def get(self, key: str) -> Optional[Any]:
        """Get value from persistent cache."""
        file_path = self._get_file_path(key)

        if not file_path.exists():
            self.miss_count += 1
            return None

        try:
            with open(file_path, 'rb') as f:
                entry_data = pickle.load(f)

            entry = CacheEntry(**entry_data)

            # Check expiration
            if entry.is_expired():
                file_path.unlink()
                self.miss_count += 1
                return None

            # Update access time
            entry.touch()

            # Save updated entry
            with open(file_path, 'wb') as f:
                pickle.dump(entry.dict(), f)

            self.hit_count += 1
            return entry.value

        except Exception as e:
            self.logger.error(f"Failed to load cache entry {key}: {e}")
            # Remove corrupted file
            file_path.unlink(missing_ok=True)
            self.miss_count += 1
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set value in persistent cache."""
        file_path = self._get_file_path(key)

        entry = CacheEntry(
            key=key,
            value=value,
            ttl_seconds=ttl
        )

        try:
            with open(file_path, 'wb') as f:
                pickle.dump(entry.dict(), f)

            self.logger.debug(f"Persisted cache key: {key}")

            # Check cache size and cleanup if needed
            self._cleanup_if_oversized()

        except Exception as e:
            self.logger.error(f"Failed to persist cache entry {key}: {e}")

    def delete(self, key: str) -> bool:
        """Delete key from persistent cache."""
        file_path = self._get_file_path(key)

        if file_path.exists():
            file_path.unlink()
            return True

        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = 0
        for file_path in self.cache_dir.glob("*.cache"):
            file_path.unlink()
            count += 1

        self.logger.info(f"Cleared {count} persistent cache entries")

    def _get_cache_size_mb(self) -> float:
        """Get total cache size in MB."""
        total_size = 0
        for file_path in self.cache_dir.glob("*.cache"):
            try:
                total_size += file_path.stat().st_size
            except (OSError, FileNotFoundError):
                pass

        return total_size / 1024 / 1024  # Convert to MB

    def _cleanup_if_oversized(self) -> None:
        """Clean up cache if it exceeds size limit."""
        current_size = self._get_cache_size_mb()

        if current_size <= self.max_size_mb:
            return

        # Get all cache files with their modification times
        files = []
        for file_path in self.cache_dir.glob("*.cache"):
            try:
                mtime = file_path.stat().st_mtime
                files.append((file_path, mtime))
            except (OSError, FileNotFoundError):
                pass

        # Sort by modification time (oldest first)
        files.sort(key=lambda x: x[1])

        # Remove oldest files until under size limit
        removed_count = 0
        for file_path, _ in files:
            file_path.unlink(missing_ok=True)
            removed_count += 1

            if self._get_cache_size_mb() <= self.max_size_mb * 0.8:  # 80% of limit
                break

        if removed_count > 0:
            self.logger.info(f"Cleaned up {removed_count} cache files to maintain size limit")

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired_count = 0

        for file_path in self.cache_dir.glob("*.cache"):
            try:
                with open(file_path, 'rb') as f:
                    entry_data = pickle.load(f)

                entry = CacheEntry(**entry_data)

                if entry.is_expired():
                    file_path.unlink()
                    expired_count += 1

            except Exception:
                # Remove corrupted files
                file_path.unlink(missing_ok=True)
                expired_count += 1

        if expired_count > 0:
            self.logger.info(f"Cleaned up {expired_count} expired/corrupted cache entries")

        return expired_count

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0

        file_count = len(list(self.cache_dir.glob("*.cache")))
        cache_size_mb = self._get_cache_size_mb()

        return {
            "type": "persistent",
            "cache_dir": str(self.cache_dir),
            "max_size_mb": self.max_size_mb,
            "current_size_mb": cache_size_mb,
            "file_count": file_count,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate_percent": hit_rate
        }


class CacheManager:
    """High-level cache manager with multiple cache layers."""

    def __init__(self, memory_cache_size: int = 1000,
                 persistent_cache_dir: Optional[Path] = None,
                 persistent_cache_size_mb: float = 100.0):
        """Initialize cache manager."""
        self.logger = get_logger(__name__)

        # Memory cache (L1)
        self.memory_cache = MemoryCache(max_size=memory_cache_size)

        # Persistent cache (L2)
        self.persistent_cache: Optional[PersistentCache] = None
        if persistent_cache_dir:
            self.persistent_cache = PersistentCache(
                persistent_cache_dir,
                persistent_cache_size_mb
            )

        # Cache keys by category for easier management
        self.instrument_configs: Dict[str, str] = {}
        self.measurement_cache: Dict[str, str] = {}
        self.calibration_cache: Dict[str, str] = {}

        self.logger.info("Cache manager initialized")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache (checks L1 then L2)."""
        # Try memory cache first
        value = self.memory_cache.get(key)
        if value is not None:
            return value

        # Try persistent cache
        if self.persistent_cache:
            value = self.persistent_cache.get(key)
            if value is not None:
                # Promote to memory cache
                self.memory_cache.set(key, value)
                return value

        return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None,
            persist: bool = False) -> None:
        """Set value in cache."""
        # Always set in memory cache
        self.memory_cache.set(key, value, ttl)

        # Optionally persist to disk
        if persist and self.persistent_cache:
            self.persistent_cache.set(key, value, ttl)

    def delete(self, key: str) -> bool:
        """Delete key from all cache levels."""
        deleted = False

        if self.memory_cache.delete(key):
            deleted = True

        if self.persistent_cache and self.persistent_cache.delete(key):
            deleted = True

        return deleted

    def clear(self) -> None:
        """Clear all cache levels."""
        self.memory_cache.clear()
        if self.persistent_cache:
            self.persistent_cache.clear()

        self.instrument_configs.clear()
        self.measurement_cache.clear()
        self.calibration_cache.clear()

    # Specialized caching methods

    def cache_instrument_config(self, instrument_id: str, config: Dict[str, Any],
                               ttl: Optional[float] = 3600) -> None:
        """Cache instrument configuration."""
        key = f"instrument_config:{instrument_id}"
        self.set(key, config, ttl, persist=True)
        self.instrument_configs[instrument_id] = key

    def get_instrument_config(self, instrument_id: str) -> Optional[Dict[str, Any]]:
        """Get cached instrument configuration."""
        key = f"instrument_config:{instrument_id}"
        return self.get(key)

    def cache_measurement(self, instrument_id: str, measurement_type: str,
                         parameters: Dict[str, Any], result: Any,
                         ttl: Optional[float] = 300) -> None:
        """Cache measurement result."""
        # Create cache key from parameters
        param_hash = hashlib.sha256(str(sorted(parameters.items())).encode()).hexdigest()[:16]
        key = f"measurement:{instrument_id}:{measurement_type}:{param_hash}"

        cache_data = {
            "result": result,
            "parameters": parameters,
            "timestamp": datetime.utcnow().isoformat()
        }

        self.set(key, cache_data, ttl)
        self.measurement_cache[f"{instrument_id}:{measurement_type}"] = key

    def get_cached_measurement(self, instrument_id: str, measurement_type: str,
                              parameters: Dict[str, Any]) -> Optional[Any]:
        """Get cached measurement result."""
        param_hash = hashlib.sha256(str(sorted(parameters.items())).encode()).hexdigest()[:16]
        key = f"measurement:{instrument_id}:{measurement_type}:{param_hash}"

        cache_data = self.get(key)
        if cache_data:
            return cache_data["result"]

        return None

    def cache_calibration_data(self, instrument_id: str, calibration_data: Dict[str, Any],
                              ttl: Optional[float] = 86400) -> None:  # 24 hours
        """Cache instrument calibration data."""
        key = f"calibration:{instrument_id}"
        self.set(key, calibration_data, ttl, persist=True)
        self.calibration_cache[instrument_id] = key

    def get_calibration_data(self, instrument_id: str) -> Optional[Dict[str, Any]]:
        """Get cached calibration data."""
        key = f"calibration:{instrument_id}"
        return self.get(key)

    def cleanup_expired(self) -> Dict[str, int]:
        """Clean up expired entries in all cache levels."""
        results = {}

        results["memory"] = self.memory_cache.cleanup_expired()

        if self.persistent_cache:
            results["persistent"] = self.persistent_cache.cleanup_expired()

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        stats = {
            "memory_cache": self.memory_cache.get_stats(),
            "persistent_cache": None,
            "cached_items": {
                "instrument_configs": len(self.instrument_configs),
                "measurements": len(self.measurement_cache),
                "calibrations": len(self.calibration_cache)
            }
        }

        if self.persistent_cache:
            stats["persistent_cache"] = self.persistent_cache.get_stats()

        return stats

    def optimize_cache(self) -> Dict[str, Any]:
        """Optimize cache performance."""
        optimization_results = {
            "expired_cleaned": self.cleanup_expired(),
            "recommendations": []
        }

        memory_stats = self.memory_cache.get_stats()
        hit_rate = memory_stats["hit_rate_percent"]

        if hit_rate < 70:
            optimization_results["recommendations"].append(
                "Consider increasing memory cache size for better hit rate"
            )

        if memory_stats["eviction_count"] > memory_stats["hit_count"] * 0.1:
            optimization_results["recommendations"].append(
                "High eviction rate detected - consider increasing cache size or adjusting TTL"
            )

        return optimization_results