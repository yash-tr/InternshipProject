"""
Comprehensive Caching Service.

This service provides multi-layer caching for enrichment data, LLM responses,
TTS audio, and other expensive operations with intelligent cache management.
"""

import asyncio
import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Union, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import logging

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_async_session

logger = logging.getLogger(__name__)


class CacheType(str, Enum):
    """Types of cached data."""
    ENRICHMENT = "enrichment"
    CLASSIFIER = "classifier"
    PLANNER = "planner"
    TTS_AUDIO = "tts_audio"
    PROSPECT_RESEARCH = "prospect_research"
    COMPANY_DATA = "company_data"
    CALL_PLANS = "call_plans"
    OBJECTION_RESPONSES = "objection_responses"


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    data: Any
    cache_type: CacheType
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size_bytes: int = 0
    tags: List[str] = None


@dataclass
class CacheStats:
    """Cache performance statistics."""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    hit_rate: float = 0.0
    total_size_bytes: int = 0
    entry_count: int = 0
    evictions: int = 0
    errors: int = 0


class ComprehensiveCachingService:
    """
    Multi-layer caching service with intelligent cache management,
    performance optimization, and cost tracking.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Redis client for primary caching
        self.redis_client: Optional[redis.Redis] = None
        
        # Cache configuration
        self._cache_configs = {
            CacheType.ENRICHMENT: {
                "ttl": 7 * 24 * 3600,  # 7 days
                "max_size": 1000,
                "compression": True,
                "tags": ["prospect", "company"]
            },
            CacheType.CLASSIFIER: {
                "ttl": 24 * 3600,  # 24 hours
                "max_size": 5000,
                "compression": False,
                "tags": ["llm", "classification"]
            },
            CacheType.PLANNER: {
                "ttl": 24 * 3600,  # 24 hours
                "max_size": 2000,
                "compression": True,
                "tags": ["llm", "planning"]
            },
            CacheType.TTS_AUDIO: {
                "ttl": 30 * 24 * 3600,  # 30 days
                "max_size": 10000,
                "compression": False,
                "tags": ["audio", "tts"]
            },
            CacheType.PROSPECT_RESEARCH: {
                "ttl": 7 * 24 * 3600,  # 7 days
                "max_size": 3000,
                "compression": True,
                "tags": ["research", "prospect"]
            },
            CacheType.COMPANY_DATA: {
                "ttl": 14 * 24 * 3600,  # 14 days
                "max_size": 2000,
                "compression": True,
                "tags": ["company", "enrichment"]
            },
            CacheType.CALL_PLANS: {
                "ttl": 24 * 3600,  # 24 hours
                "max_size": 1000,
                "compression": True,
                "tags": ["calling", "planning"]
            },
            CacheType.OBJECTION_RESPONSES: {
                "ttl": 7 * 24 * 3600,  # 7 days
                "max_size": 5000,
                "compression": False,
                "tags": ["objections", "responses"]
            }
        }
        
        # Performance tracking
        self._stats = CacheStats()
        self._stats_lock = asyncio.Lock()
        
        # Cache warming strategies
        self._warming_strategies: Dict[CacheType, Callable] = {}
        
        # Background tasks
        self._maintenance_task: Optional[asyncio.Task] = None
        self._stats_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize the caching service."""
        try:
            # Initialize Redis connection
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False  # Handle binary data for audio
            )
            
            # Test connection
            await self.redis_client.ping()
            
            # Start background tasks
            self._maintenance_task = asyncio.create_task(self._maintenance_loop())
            self._stats_task = asyncio.create_task(self._stats_collection_loop())
            
            # Initialize cache warming
            await self._initialize_cache_warming()
            
            self.logger.info("Comprehensive caching service initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize caching service: {e}")
            raise
    
    async def get(self, 
                 cache_type: CacheType, 
                 key: str, 
                 default: Any = None) -> Any:
        """
        Get data from cache with performance tracking.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached data or default value
        """
        cache_key = self._build_cache_key(cache_type, key)
        
        try:
            async with self._stats_lock:
                self._stats.total_requests += 1
            
            # Try to get from Redis
            cached_data = await self.redis_client.get(cache_key)
            
            if cached_data is not None:
                # Cache hit
                async with self._stats_lock:
                    self._stats.cache_hits += 1
                    self._stats.hit_rate = self._stats.cache_hits / self._stats.total_requests
                
                # Update access tracking
                await self._update_access_tracking(cache_key)
                
                # Deserialize data
                try:
                    if cache_type == CacheType.TTS_AUDIO:
                        # Return binary data as-is for audio
                        return cached_data
                    else:
                        # JSON deserialize for other data types
                        return json.loads(cached_data.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    self.logger.error(f"Cache deserialization error for {cache_key}: {e}")
                    return default
            else:
                # Cache miss
                async with self._stats_lock:
                    self._stats.cache_misses += 1
                    self._stats.hit_rate = self._stats.cache_hits / self._stats.total_requests
                
                return default
                
        except Exception as e:
            self.logger.error(f"Cache get error for {cache_key}: {e}")
            async with self._stats_lock:
                self._stats.errors += 1
            return default
    
    async def set(self, 
                 cache_type: CacheType, 
                 key: str, 
                 data: Any, 
                 ttl: Optional[int] = None,
                 tags: Optional[List[str]] = None) -> bool:
        """
        Set data in cache with appropriate configuration.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            data: Data to cache
            ttl: Time to live (override default)
            tags: Additional tags for the entry
            
        Returns:
            True if successful
        """
        cache_key = self._build_cache_key(cache_type, key)
        config = self._cache_configs.get(cache_type, {})
        
        try:
            # Serialize data
            if cache_type == CacheType.TTS_AUDIO:
                # Handle binary audio data
                serialized_data = data if isinstance(data, bytes) else data.encode()
            else:
                # JSON serialize for other data types
                serialized_data = json.dumps(data, default=str).encode('utf-8')
            
            # Calculate size
            size_bytes = len(serialized_data)
            
            # Check size limits
            max_size = config.get("max_size", 10000)
            if size_bytes > max_size * 1024:  # Convert KB to bytes
                self.logger.warning(f"Cache entry too large: {size_bytes} bytes > {max_size}KB")
                return False
            
            # Set TTL
            cache_ttl = ttl or config.get("ttl", 3600)
            
            # Store in Redis
            await self.redis_client.setex(cache_key, cache_ttl, serialized_data)
            
            # Store metadata
            metadata = {
                "cache_type": cache_type.value,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(seconds=cache_ttl)).isoformat(),
                "size_bytes": size_bytes,
                "tags": tags or config.get("tags", [])
            }
            
            metadata_key = f"{cache_key}:meta"
            await self.redis_client.setex(
                metadata_key, 
                cache_ttl, 
                json.dumps(metadata).encode('utf-8')
            )
            
            # Update stats
            async with self._stats_lock:
                self._stats.total_size_bytes += size_bytes
                self._stats.entry_count += 1
            
            return True
            
        except Exception as e:
            self.logger.error(f"Cache set error for {cache_key}: {e}")
            async with self._stats_lock:
                self._stats.errors += 1
            return False
    
    async def delete(self, cache_type: CacheType, key: str) -> bool:
        """
        Delete entry from cache.
        
        Args:
            cache_type: Type of cached data
            key: Cache key
            
        Returns:
            True if deleted
        """
        cache_key = self._build_cache_key(cache_type, key)
        
        try:
            # Get metadata before deletion for stats
            metadata_key = f"{cache_key}:meta"
            metadata = await self.redis_client.get(metadata_key)
            
            # Delete both data and metadata
            deleted_count = await self.redis_client.delete(cache_key, metadata_key)
            
            # Update stats
            if metadata and deleted_count > 0:
                try:
                    meta_data = json.loads(metadata.decode('utf-8'))
                    size_bytes = meta_data.get("size_bytes", 0)
                    
                    async with self._stats_lock:
                        self._stats.total_size_bytes = max(0, self._stats.total_size_bytes - size_bytes)
                        self._stats.entry_count = max(0, self._stats.entry_count - 1)
                except:
                    pass
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"Cache delete error for {cache_key}: {e}")
            return False
    
    async def clear_by_type(self, cache_type: CacheType) -> int:
        """
        Clear all entries of a specific type.
        
        Args:
            cache_type: Type of cached data to clear
            
        Returns:
            Number of entries cleared
        """
        try:
            pattern = f"cache:{cache_type.value}:*"
            keys = await self.redis_client.keys(pattern)
            
            if keys:
                deleted_count = await self.redis_client.delete(*keys)
                
                # Also delete metadata keys
                meta_keys = [f"{key}:meta" for key in keys]
                await self.redis_client.delete(*meta_keys)
                
                self.logger.info(f"Cleared {deleted_count} entries of type {cache_type.value}")
                return deleted_count
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache type {cache_type.value}: {e}")
            return 0
    
    async def clear_by_tags(self, tags: List[str]) -> int:
        """
        Clear all entries with specific tags.
        
        Args:
            tags: Tags to match
            
        Returns:
            Number of entries cleared
        """
        try:
            cleared_count = 0
            
            # Scan all metadata keys
            async for key in self.redis_client.scan_iter(match="cache:*:meta"):
                try:
                    metadata = await self.redis_client.get(key)
                    if metadata:
                        meta_data = json.loads(metadata.decode('utf-8'))
                        entry_tags = meta_data.get("tags", [])
                        
                        # Check if any of the specified tags match
                        if any(tag in entry_tags for tag in tags):
                            # Delete the entry and its metadata
                            data_key = key.replace(":meta", "")
                            deleted = await self.redis_client.delete(data_key, key)
                            if deleted > 0:
                                cleared_count += 1
                except:
                    continue
            
            self.logger.info(f"Cleared {cleared_count} entries with tags {tags}")
            return cleared_count
            
        except Exception as e:
            self.logger.error(f"Failed to clear cache by tags {tags}: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            async with self._stats_lock:
                base_stats = {
                    "total_requests": self._stats.total_requests,
                    "cache_hits": self._stats.cache_hits,
                    "cache_misses": self._stats.cache_misses,
                    "hit_rate": self._stats.hit_rate,
                    "total_size_bytes": self._stats.total_size_bytes,
                    "entry_count": self._stats.entry_count,
                    "evictions": self._stats.evictions,
                    "errors": self._stats.errors
                }
            
            # Get Redis info
            redis_info = await self.redis_client.info("memory")
            
            # Get per-type statistics
            type_stats = {}
            for cache_type in CacheType:
                pattern = f"cache:{cache_type.value}:*"
                keys = await self.redis_client.keys(pattern)
                type_stats[cache_type.value] = {
                    "entry_count": len([k for k in keys if not k.endswith(":meta")]),
                    "config": self._cache_configs.get(cache_type, {})
                }
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "overall": base_stats,
                "redis_memory": {
                    "used_memory": redis_info.get("used_memory", 0),
                    "used_memory_human": redis_info.get("used_memory_human", "0B"),
                    "maxmemory": redis_info.get("maxmemory", 0)
                },
                "by_type": type_stats,
                "performance_alerts": await self._check_performance_alerts()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
    
    async def warm_cache(self, cache_type: CacheType, keys: List[str]) -> Dict[str, Any]:
        """
        Warm cache with specific keys.
        
        Args:
            cache_type: Type of cache to warm
            keys: Keys to warm
            
        Returns:
            Warming results
        """
        try:
            warming_strategy = self._warming_strategies.get(cache_type)
            if not warming_strategy:
                return {"error": f"No warming strategy for {cache_type.value}"}
            
            warmed_count = 0
            failed_count = 0
            
            for key in keys:
                try:
                    # Check if already cached
                    existing = await self.get(cache_type, key)
                    if existing is not None:
                        continue
                    
                    # Generate data using warming strategy
                    data = await warming_strategy(key)
                    if data is not None:
                        success = await self.set(cache_type, key, data)
                        if success:
                            warmed_count += 1
                        else:
                            failed_count += 1
                    else:
                        failed_count += 1
                        
                except Exception as e:
                    self.logger.error(f"Failed to warm cache key {key}: {e}")
                    failed_count += 1
            
            return {
                "cache_type": cache_type.value,
                "requested_keys": len(keys),
                "warmed_count": warmed_count,
                "failed_count": failed_count,
                "success_rate": warmed_count / len(keys) if keys else 0
            }
            
        except Exception as e:
            self.logger.error(f"Cache warming failed for {cache_type.value}: {e}")
            return {"error": str(e)}
    
    def register_warming_strategy(self, 
                                cache_type: CacheType, 
                                strategy: Callable[[str], Any]):
        """
        Register a cache warming strategy for a specific type.
        
        Args:
            cache_type: Type of cache
            strategy: Async function that generates data for a key
        """
        self._warming_strategies[cache_type] = strategy
        self.logger.info(f"Registered warming strategy for {cache_type.value}")
    
    # Private helper methods
    
    def _build_cache_key(self, cache_type: CacheType, key: str) -> str:
        """Build a standardized cache key."""
        # Hash long keys to avoid Redis key length limits
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"cache:{cache_type.value}:{key_hash}"
        else:
            return f"cache:{cache_type.value}:{key}"
    
    async def _update_access_tracking(self, cache_key: str):
        """Update access tracking for cache entry."""
        try:
            metadata_key = f"{cache_key}:meta"
            metadata = await self.redis_client.get(metadata_key)
            
            if metadata:
                meta_data = json.loads(metadata.decode('utf-8'))
                meta_data["access_count"] = meta_data.get("access_count", 0) + 1
                meta_data["last_accessed"] = datetime.utcnow().isoformat()
                
                # Update metadata with same TTL as original
                ttl = await self.redis_client.ttl(cache_key)
                if ttl > 0:
                    await self.redis_client.setex(
                        metadata_key,
                        ttl,
                        json.dumps(meta_data).encode('utf-8')
                    )
        except:
            # Don't fail cache operations due to tracking errors
            pass
    
    async def _check_performance_alerts(self) -> List[Dict[str, Any]]:
        """Check for cache performance alerts."""
        alerts = []
        
        # Check hit rate
        if self._stats.total_requests > 100 and self._stats.hit_rate < 0.3:
            alerts.append({
                "type": "low_hit_rate",
                "message": f"Cache hit rate ({self._stats.hit_rate:.2%}) below 30% threshold",
                "severity": "warning"
            })
        
        # Check error rate
        if self._stats.total_requests > 0:
            error_rate = self._stats.errors / self._stats.total_requests
            if error_rate > 0.05:  # 5% error rate
                alerts.append({
                    "type": "high_error_rate",
                    "message": f"Cache error rate ({error_rate:.2%}) above 5% threshold",
                    "severity": "critical"
                })
        
        # Check memory usage (would need Redis info)
        try:
            redis_info = await self.redis_client.info("memory")
            used_memory = redis_info.get("used_memory", 0)
            max_memory = redis_info.get("maxmemory", 0)
            
            if max_memory > 0:
                memory_usage = used_memory / max_memory
                if memory_usage > 0.8:  # 80% memory usage
                    alerts.append({
                        "type": "high_memory_usage",
                        "message": f"Redis memory usage ({memory_usage:.2%}) above 80% threshold",
                        "severity": "warning"
                    })
        except:
            pass
        
        return alerts
    
    async def _initialize_cache_warming(self):
        """Initialize cache warming strategies."""
        # This would register warming strategies for different cache types
        # For now, we'll just log that it's initialized
        self.logger.info("Cache warming strategies initialized")
    
    # Background tasks
    
    async def _maintenance_loop(self):
        """Background maintenance loop."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Perform cache maintenance
                await self._perform_maintenance()
                
            except Exception as e:
                self.logger.error(f"Cache maintenance error: {e}")
    
    async def _stats_collection_loop(self):
        """Background stats collection loop."""
        while True:
            try:
                await asyncio.sleep(60)  # Collect stats every minute
                
                # Update entry count and size from Redis
                await self._update_stats_from_redis()
                
            except Exception as e:
                self.logger.error(f"Stats collection error: {e}")
    
    async def _perform_maintenance(self):
        """Perform cache maintenance tasks."""
        try:
            # Clean up expired entries (Redis handles this automatically)
            # But we can clean up orphaned metadata
            
            # Check for performance issues
            alerts = await self._check_performance_alerts()
            for alert in alerts:
                self.logger.warning(f"Cache performance alert: {alert['message']}")
            
            # Log maintenance completion
            self.logger.debug("Cache maintenance completed")
            
        except Exception as e:
            self.logger.error(f"Cache maintenance failed: {e}")
    
    async def _update_stats_from_redis(self):
        """Update statistics from Redis."""
        try:
            # Count total entries
            all_keys = await self.redis_client.keys("cache:*")
            data_keys = [k for k in all_keys if not k.endswith(":meta")]
            
            async with self._stats_lock:
                self._stats.entry_count = len(data_keys)
            
        except Exception as e:
            self.logger.error(f"Failed to update stats from Redis: {e}")


# Global instance
comprehensive_caching_service = ComprehensiveCachingService()