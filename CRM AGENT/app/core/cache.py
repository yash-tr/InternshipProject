"""
Comprehensive caching layer for performance optimization.
"""
import json
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Union
from functools import wraps

import structlog
import redis.asyncio as redis
from pydantic import BaseModel

from app.core.config import get_settings

logger = structlog.get_logger()


class CacheConfig:
    """Cache configuration and TTL settings."""
    
    # Cache TTL settings (in seconds)
    ENRICHMENT_TTL = 7 * 24 * 3600  # 7 days
    CLASSIFIER_TTL = 24 * 3600      # 24 hours
    PLAN_TTL = 24 * 3600            # 24 hours
    TTS_TTL = 30 * 24 * 3600        # 30 days
    CONTACT_TTL = 6 * 3600          # 6 hours
    LEAD_SCORE_TTL = 2 * 3600       # 2 hours
    API_RESPONSE_TTL = 1800         # 30 minutes
    
    # Cache key prefixes
    ENRICHMENT_PREFIX = "enrichment"
    CLASSIFIER_PREFIX = "classifier"
    PLAN_PREFIX = "plan"
    TTS_PREFIX = "tts"
    CONTACT_PREFIX = "contact"
    LEAD_SCORE_PREFIX = "lead_score"
    API_RESPONSE_PREFIX = "api_response"


class CacheManager:
    """Advanced caching manager with Redis backend."""
    
    def __init__(self):
        self.settings = get_settings()
        self.redis_client: Optional[redis.Redis] = None
        self.local_cache: Dict[str, Dict] = {}  # Fallback local cache
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0,
            'errors': 0
        }
    
    async def initialize(self):
        """Initialize Redis connection."""
        try:
            self.redis_client = redis.from_url(
                self.settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={},
                health_check_interval=30
            )
            
            # Test connection
            await self.redis_client.ping()
            logger.info("Redis cache initialized successfully")
            
        except Exception as e:
            logger.warning("Redis unavailable, using local cache fallback", error=str(e))
            self.redis_client = None
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
    
    def _generate_key(self, prefix: str, identifier: str, context: Optional[str] = None) -> str:
        """Generate cache key with optional context hash."""
        if context:
            context_hash = hashlib.md5(context.encode()).hexdigest()[:8]
            return f"{prefix}:{identifier}:{context_hash}"
        return f"{prefix}:{identifier}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            if self.redis_client:
                value = await self.redis_client.get(key)
                if value:
                    self.cache_stats['hits'] += 1
                    return json.loads(value)
                else:
                    self.cache_stats['misses'] += 1
                    return None
            else:
                # Fallback to local cache
                cache_entry = self.local_cache.get(key)
                if cache_entry and cache_entry['expires'] > datetime.utcnow():
                    self.cache_stats['hits'] += 1
                    return cache_entry['value']
                else:
                    self.cache_stats['misses'] += 1
                    return None
                    
        except Exception as e:
            logger.error("Cache get error", key=key, error=str(e))
            self.cache_stats['errors'] += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache."""
        try:
            serialized_value = json.dumps(value, default=str)
            
            if self.redis_client:
                await self.redis_client.setex(key, ttl, serialized_value)
            else:
                # Fallback to local cache
                self.local_cache[key] = {
                    'value': value,
                    'expires': datetime.utcnow() + timedelta(seconds=ttl)
                }
            
            self.cache_stats['sets'] += 1
            return True
            
        except Exception as e:
            logger.error("Cache set error", key=key, error=str(e))
            self.cache_stats['errors'] += 1
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        try:
            if self.redis_client:
                await self.redis_client.delete(key)
            else:
                self.local_cache.pop(key, None)
            
            self.cache_stats['deletes'] += 1
            return True
            
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
            self.cache_stats['errors'] += 1
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching pattern."""
        try:
            if self.redis_client:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    deleted = await self.redis_client.delete(*keys)
                    self.cache_stats['deletes'] += deleted
                    return deleted
            else:
                # Clear from local cache
                keys_to_delete = [k for k in self.local_cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self.local_cache[key]
                self.cache_stats['deletes'] += len(keys_to_delete)
                return len(keys_to_delete)
            
            return 0
            
        except Exception as e:
            logger.error("Cache clear pattern error", pattern=pattern, error=str(e))
            self.cache_stats['errors'] += 1
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            **self.cache_stats,
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests
        }
    
    # Specialized cache methods for different data types
    
    async def get_enrichment_data(self, domain: str, company: str) -> Optional[Dict]:
        """Get cached enrichment data."""
        key = self._generate_key(CacheConfig.ENRICHMENT_PREFIX, f"{domain}|{company}")
        return await self.get(key)
    
    async def set_enrichment_data(self, domain: str, company: str, data: Dict) -> bool:
        """Cache enrichment data."""
        key = self._generate_key(CacheConfig.ENRICHMENT_PREFIX, f"{domain}|{company}")
        return await self.set(key, data, CacheConfig.ENRICHMENT_TTL)
    
    async def get_classifier_result(self, lead_id: str) -> Optional[Dict]:
        """Get cached classifier result."""
        key = self._generate_key(CacheConfig.CLASSIFIER_PREFIX, lead_id)
        return await self.get(key)
    
    async def set_classifier_result(self, lead_id: str, result: Dict) -> bool:
        """Cache classifier result."""
        key = self._generate_key(CacheConfig.CLASSIFIER_PREFIX, lead_id)
        return await self.set(key, result, CacheConfig.CLASSIFIER_TTL)
    
    async def get_call_plan(self, lead_id: str, context_hash: str) -> Optional[Dict]:
        """Get cached call plan."""
        key = self._generate_key(CacheConfig.PLAN_PREFIX, lead_id, context_hash)
        return await self.get(key)
    
    async def set_call_plan(self, lead_id: str, context_hash: str, plan: Dict) -> bool:
        """Cache call plan."""
        key = self._generate_key(CacheConfig.PLAN_PREFIX, lead_id, context_hash)
        return await self.set(key, plan, CacheConfig.PLAN_TTL)
    
    async def get_tts_audio(self, prompt_hash: str) -> Optional[str]:
        """Get cached TTS audio."""
        key = self._generate_key(CacheConfig.TTS_PREFIX, prompt_hash)
        return await self.get(key)
    
    async def set_tts_audio(self, prompt_hash: str, audio_url: str) -> bool:
        """Cache TTS audio."""
        key = self._generate_key(CacheConfig.TTS_PREFIX, prompt_hash)
        return await self.set(key, audio_url, CacheConfig.TTS_TTL)
    
    async def get_contact_data(self, phone: str) -> Optional[Dict]:
        """Get cached contact data."""
        key = self._generate_key(CacheConfig.CONTACT_PREFIX, phone)
        return await self.get(key)
    
    async def set_contact_data(self, phone: str, data: Dict) -> bool:
        """Cache contact data."""
        key = self._generate_key(CacheConfig.CONTACT_PREFIX, phone)
        return await self.set(key, data, CacheConfig.CONTACT_TTL)


# Global cache manager instance
cache_manager = CacheManager()


def cached(ttl: int = 3600, key_prefix: str = "default"):
    """Decorator for caching function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
            cache_key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            # Try to get from cache
            cached_result = await cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_manager.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


class CacheWarmer:
    """Background cache warming for frequently accessed data."""
    
    def __init__(self, cache_manager: CacheManager):
        self.cache_manager = cache_manager
        self.warming_tasks = []
    
    async def warm_contact_cache(self, phone_numbers: list):
        """Pre-warm contact cache for upcoming calls."""
        from app.services.salesforce import SalesforceService
        
        sf_service = SalesforceService()
        
        for phone in phone_numbers:
            try:
                # Check if already cached
                cached = await self.cache_manager.get_contact_data(phone)
                if not cached:
                    # Fetch and cache contact data
                    contact_data = await sf_service.find_contact_by_phone(phone)
                    if contact_data:
                        await self.cache_manager.set_contact_data(phone, contact_data)
                        logger.debug("Warmed contact cache", phone=phone)
            except Exception as e:
                logger.error("Failed to warm contact cache", phone=phone, error=str(e))
    
    async def warm_enrichment_cache(self, companies: list):
        """Pre-warm enrichment cache for companies."""
        from app.services.web_scraping import WebScrapingService
        
        scraping_service = WebScrapingService()
        
        for company_data in companies:
            try:
                domain = company_data.get('domain')
                company_name = company_data.get('name')
                
                if domain and company_name:
                    cached = await self.cache_manager.get_enrichment_data(domain, company_name)
                    if not cached:
                        # Fetch and cache enrichment data
                        enrichment_data = await scraping_service.enrich_company_data(domain, company_name)
                        if enrichment_data:
                            await self.cache_manager.set_enrichment_data(domain, company_name, enrichment_data)
                            logger.debug("Warmed enrichment cache", domain=domain, company=company_name)
            except Exception as e:
                logger.error("Failed to warm enrichment cache", company=company_data, error=str(e))


# Global cache warmer instance
cache_warmer = CacheWarmer(cache_manager)