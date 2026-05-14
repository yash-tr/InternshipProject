"""
Selective LLM Service for Complex Scenarios

This module implements selective LLM usage with strict budget controls,
caching strategies, and fallback mechanisms for the AI Calling Agent MVP.
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

import structlog

from ..core.config import get_settings
from ..services.openrouter_llm import OpenRouterLLMService, TokenUsage

logger = structlog.get_logger()


class LLMUsageType(str, Enum):
    """Types of LLM usage for budget tracking."""
    PLANNER = "planner"           # Pre-call planning (1 call per lead, 24h cache)
    CLASSIFIER = "classifier"     # Objection classification (64 token limit)
    RUNTIME = "runtime"          # Runtime complex scenarios (80 token limit)


class ProspectTier(str, Enum):
    """Prospect value tiers for budget allocation."""
    NON_VIP = "non_vip"          # Standard prospects (limited LLM usage)
    VIP = "vip"                  # High-value prospects (extended LLM usage)


@dataclass
class LLMBudgetLimits:
    """Budget limits for different LLM usage types."""
    # Token limits per call
    classifier_max_tokens: int = 64
    planner_max_tokens: int = 600
    runtime_max_tokens: int = 80
    
    # Call limits per conversation
    planner_calls_limit: int = 1      # 1 call per lead (cached 24h)
    runtime_calls_non_vip: int = 1    # Max 1 runtime call for non-VIP
    runtime_calls_vip: int = 3        # Max 3 runtime calls for VIP
    
    # Cache TTL settings
    planner_cache_ttl: int = 86400    # 24 hours
    classifier_cache_ttl: int = 86400  # 24 hours
    
    # Daily budget limits
    daily_token_limit: int = 100000   # 100k tokens per day
    daily_cost_limit: float = 50.0    # $50 per day


@dataclass
class LLMUsageTracker:
    """Tracks LLM usage for budget enforcement."""
    lead_id: str
    prospect_tier: ProspectTier
    
    # Usage counters
    planner_calls: int = 0
    classifier_calls: int = 0
    runtime_calls: int = 0
    
    # Token usage
    total_tokens_used: int = 0
    tokens_by_type: Dict[LLMUsageType, int] = field(default_factory=dict)
    
    # Cost tracking
    estimated_cost: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def can_use_llm(self, usage_type: LLMUsageType, budget_limits: LLMBudgetLimits) -> bool:
        """Check if LLM usage is within budget limits."""
        if usage_type == LLMUsageType.PLANNER:
            return self.planner_calls < budget_limits.planner_calls_limit
        
        elif usage_type == LLMUsageType.RUNTIME:
            max_calls = (budget_limits.runtime_calls_vip 
                        if self.prospect_tier == ProspectTier.VIP 
                        else budget_limits.runtime_calls_non_vip)
            return self.runtime_calls < max_calls
        
        elif usage_type == LLMUsageType.CLASSIFIER:
            # Classifier has no hard call limit, but respects daily limits
            return True
        
        return False
    
    def record_usage(self, usage_type: LLMUsageType, tokens_used: int, cost: float = 0.0):
        """Record LLM usage."""
        if usage_type == LLMUsageType.PLANNER:
            self.planner_calls += 1
        elif usage_type == LLMUsageType.CLASSIFIER:
            self.classifier_calls += 1
        elif usage_type == LLMUsageType.RUNTIME:
            self.runtime_calls += 1
        
        self.total_tokens_used += tokens_used
        self.tokens_by_type[usage_type] = self.tokens_by_type.get(usage_type, 0) + tokens_used
        self.estimated_cost += cost
        self.last_updated = datetime.utcnow()


class SelectiveLLMService:
    """
    Selective LLM service with budget controls and caching.
    
    Implements cost-controlled LLM usage with pre-call planning,
    selective runtime usage, and comprehensive caching strategies.
    """
    
    def __init__(self):
        """Initialize selective LLM service."""
        self.settings = get_settings()
        self.base_llm_service = OpenRouterLLMService()
        
        # Budget configuration
        self.budget_limits = LLMBudgetLimits()
        
        # Usage tracking
        self.usage_trackers: Dict[str, LLMUsageTracker] = {}
        self.daily_usage = TokenUsage()
        self.last_daily_reset = datetime.utcnow().date()
        
        # Simple in-memory cache (Redis would be better for production)
        self.cache: Dict[str, Dict[str, Any]] = {}
        
        # Template fallbacks
        self.template_responses = self._initialize_template_responses()
        
        # Performance tracking
        self.performance_metrics = {
            'cache_hits': 0,
            'cache_misses': 0,
            'budget_blocks': 0,
            'fallback_uses': 0,
            'total_requests': 0
        }
        
        logger.info("Selective LLM service initialized with budget controls")
    
    def _initialize_template_responses(self) -> Dict[str, str]:
        """Initialize template responses for objections."""
        return {
            'price': "I understand cost is always a consideration. Let me ask you this - what's the cost of not solving this problem? Many of our clients find the ROI becomes clear when they see the time and money they save.",
            
            'timing': "I completely understand timing is important. The good news is we can work with your timeline. What would be the ideal timeframe for you to start seeing results?",
            
            'authority': "That makes perfect sense - decisions like this often involve multiple stakeholders. Help me understand the process - who else would be involved in evaluating a solution like this?",
            
            'need': "That's great that things are working well for you. I'm curious - if you could wave a magic wand and improve one thing about your current process, what would it be?",
            
            'trust': "I completely understand your caution - that's smart business. Let me share what a similar company in your industry said after their first month with us. Would it be helpful to connect you with a reference?",
            
            'competition': "That's great that you have something in place. I'm curious - what's working well with your current solution, and if you could improve one thing about it, what would that be?",
            
            'unknown': "I appreciate you sharing that concern with me. Help me understand a bit more about what's driving that so I can address it properly."
        }


# Global service instance
selective_llm_service = SelectiveLLMService()    
async def generate_pre_call_plan(
        self,
        lead_id: str,
        prospect_data: Dict[str, Any],
        prospect_tier: ProspectTier = ProspectTier.NON_VIP
    ) -> Tuple[Optional[str], bool, Dict[str, Any]]:
        """
        Generate pre-call plan with 24-hour caching.
        
        Args:
            lead_id: Unique lead identifier
            prospect_data: Prospect information
            prospect_tier: Prospect value tier
            
        Returns:
            Tuple of (plan_text, from_cache, metadata)
        """
        self.performance_metrics['total_requests'] += 1
        
        try:
            # Get or create usage tracker
            tracker = self._get_usage_tracker(lead_id, prospect_tier)
            
            # Check budget limits
            if not tracker.can_use_llm(LLMUsageType.PLANNER, self.budget_limits):
                logger.warning("Pre-call planner budget exceeded", lead_id=lead_id)
                self.performance_metrics['budget_blocks'] += 1
                return None, False, {'error': 'budget_exceeded', 'reason': 'planner_calls_limit'}
            
            # Check daily limits
            if not await self._check_daily_limits():
                logger.warning("Daily budget limits exceeded")
                self.performance_metrics['budget_blocks'] += 1
                return None, False, {'error': 'daily_budget_exceeded'}
            
            # Generate cache key
            cache_key = self._generate_cache_key(LLMUsageType.PLANNER, lead_id, prospect_data)
            
            # Check cache first
            cached_response = self._get_cached_response(cache_key, self.budget_limits.planner_cache_ttl)
            
            if cached_response:
                logger.info("Using cached pre-call plan", lead_id=lead_id, cache_key=cache_key)
                self.performance_metrics['cache_hits'] += 1
                return cached_response['response'], True, {
                    'cached': True,
                    'created_at': cached_response['created_at'],
                    'tokens_used': cached_response['tokens_used']
                }
            
            # Generate new plan
            self.performance_metrics['cache_misses'] += 1
            plan_text, tokens_used = await self._generate_planner_response(
                prospect_data, 
                self.budget_limits.planner_max_tokens
            )
            
            # Validate response
            if not plan_text or len(plan_text.strip()) < 50:
                logger.warning("Generated plan too short, using fallback", lead_id=lead_id)
                plan_text = self._get_fallback_plan(prospect_data)
                tokens_used = 0
            
            # Record usage
            cost = self._estimate_cost(tokens_used)
            tracker.record_usage(LLMUsageType.PLANNER, tokens_used, cost)
            self._update_daily_usage(tokens_used, cost)
            
            # Cache the response
            self._cache_response(cache_key, {
                'response': plan_text,
                'tokens_used': tokens_used,
                'created_at': datetime.utcnow().isoformat(),
                'usage_type': LLMUsageType.PLANNER.value
            })
            
            logger.info(
                "Generated pre-call plan",
                lead_id=lead_id,
                tokens_used=tokens_used,
                estimated_cost=cost,
                plan_length=len(plan_text)
            )
            
            return plan_text, False, {
                'cached': False,
                'tokens_used': tokens_used,
                'estimated_cost': cost,
                'plan_length': len(plan_text)
            }
            
        except Exception as e:
            logger.error("Failed to generate pre-call plan", lead_id=lead_id, error=str(e))
            fallback_plan = self._get_fallback_plan(prospect_data)
            self.performance_metrics['fallback_uses'] += 1
            return fallback_plan, False, {'error': str(e), 'fallback': True}
    
    async def handle_complex_objection(
        self,
        lead_id: str,
        objection_text: str,
        objection_context: Dict[str, Any],
        prospect_tier: ProspectTier = ProspectTier.NON_VIP
    ) -> Tuple[Optional[str], bool, Dict[str, Any]]:
        """
        Handle complex objections with selective LLM usage.
        
        Args:
            lead_id: Unique lead identifier
            objection_text: The objection text
            objection_context: Context including prospect data and conversation history
            prospect_tier: Prospect value tier
            
        Returns:
            Tuple of (response_text, should_escalate, metadata)
        """
        self.performance_metrics['total_requests'] += 1
        
        try:
            # Get or create usage tracker
            tracker = self._get_usage_tracker(lead_id, prospect_tier)
            
            # Check if this is truly a complex objection that needs LLM
            complexity_score = self._assess_objection_complexity(objection_text, objection_context)
            
            if complexity_score < 0.7:  # Use template for simple objections
                template_response = self._get_template_objection_response(objection_text, objection_context)
                if template_response:
                    logger.info("Using template for simple objection", lead_id=lead_id, complexity=complexity_score)
                    return template_response, False, {'template_used': True, 'complexity': complexity_score}
            
            # Check budget limits for runtime LLM usage
            if not tracker.can_use_llm(LLMUsageType.RUNTIME, self.budget_limits):
                logger.warning("Runtime LLM budget exceeded, using template", lead_id=lead_id)
                self.performance_metrics['budget_blocks'] += 1
                template_response = self._get_template_objection_response(objection_text, objection_context)
                return template_response, False, {'budget_exceeded': True, 'template_fallback': True}
            
            # Check daily limits
            if not await self._check_daily_limits():
                logger.warning("Daily budget limits exceeded, using template")
                self.performance_metrics['budget_blocks'] += 1
                template_response = self._get_template_objection_response(objection_text, objection_context)
                return template_response, False, {'daily_budget_exceeded': True, 'template_fallback': True}
            
            # Generate LLM response for complex objection
            response_text, tokens_used, should_escalate = await self._generate_complex_objection_response(
                objection_text,
                objection_context,
                self.budget_limits.runtime_max_tokens
            )
            
            # Validate response
            if not response_text or len(response_text.strip()) < 20:
                logger.warning("Generated objection response too short, using template", lead_id=lead_id)
                template_response = self._get_template_objection_response(objection_text, objection_context)
                self.performance_metrics['fallback_uses'] += 1
                return template_response, False, {'llm_failed': True, 'template_fallback': True}
            
            # Record usage
            cost = self._estimate_cost(tokens_used)
            tracker.record_usage(LLMUsageType.RUNTIME, tokens_used, cost)
            self._update_daily_usage(tokens_used, cost)
            
            logger.info(
                "Generated complex objection response",
                lead_id=lead_id,
                tokens_used=tokens_used,
                estimated_cost=cost,
                should_escalate=should_escalate,
                complexity=complexity_score
            )
            
            return response_text, should_escalate, {
                'llm_used': True,
                'tokens_used': tokens_used,
                'estimated_cost': cost,
                'complexity': complexity_score,
                'should_escalate': should_escalate
            }
            
        except Exception as e:
            logger.error("Failed to handle complex objection", lead_id=lead_id, error=str(e))
            template_response = self._get_template_objection_response(objection_text, objection_context)
            self.performance_metrics['fallback_uses'] += 1
            return template_response, False, {'error': str(e), 'template_fallback': True}
    
    async def classify_objection_type(
        self,
        objection_text: str,
        context: Dict[str, Any] = None
    ) -> Tuple[str, float, Dict[str, Any]]:
        """
        Classify objection type with 64-token limit and caching.
        
        Args:
            objection_text: The objection text to classify
            context: Additional context for classification
            
        Returns:
            Tuple of (objection_type, confidence, metadata)
        """
        self.performance_metrics['total_requests'] += 1
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(LLMUsageType.CLASSIFIER, objection_text, context or {})
            
            # Check cache first
            cached_response = self._get_cached_response(cache_key, self.budget_limits.classifier_cache_ttl)
            
            if cached_response:
                logger.info("Using cached objection classification", cache_key=cache_key)
                self.performance_metrics['cache_hits'] += 1
                # Parse cached classification
                classification_data = json.loads(cached_response['response'])
                return (
                    classification_data.get('objection_type', 'unknown'),
                    classification_data.get('confidence', 0.0),
                    {'cached': True, 'created_at': cached_response['created_at']}
                )
            
            # Check daily limits
            if not await self._check_daily_limits():
                logger.warning("Daily budget limits exceeded for classification")
                self.performance_metrics['budget_blocks'] += 1
                # Use simple keyword-based classification
                objection_type, confidence = self._classify_objection_keywords(objection_text)
                return objection_type, confidence, {'keyword_classification': True, 'daily_budget_exceeded': True}
            
            # Generate classification
            self.performance_metrics['cache_misses'] += 1
            classification_result, tokens_used = await self._generate_classification_response(
                objection_text,
                context,
                self.budget_limits.classifier_max_tokens
            )
            
            # Parse classification result
            try:
                classification_data = json.loads(classification_result)
                objection_type = classification_data.get('objection_type', 'unknown')
                confidence = classification_data.get('confidence', 0.0)
            except json.JSONDecodeError:
                logger.warning("Failed to parse classification result, using keyword fallback")
                objection_type, confidence = self._classify_objection_keywords(objection_text)
                tokens_used = 0
            
            # Record usage
            cost = self._estimate_cost(tokens_used)
            self._update_daily_usage(tokens_used, cost)
            
            # Cache the response
            self._cache_response(cache_key, {
                'response': json.dumps({
                    'objection_type': objection_type,
                    'confidence': confidence
                }),
                'tokens_used': tokens_used,
                'created_at': datetime.utcnow().isoformat(),
                'usage_type': LLMUsageType.CLASSIFIER.value
            })
            
            logger.info(
                "Classified objection",
                objection_type=objection_type,
                confidence=confidence,
                tokens_used=tokens_used
            )
            
            return objection_type, confidence, {
                'cached': False,
                'tokens_used': tokens_used,
                'estimated_cost': cost
            }
            
        except Exception as e:
            logger.error("Failed to classify objection", error=str(e))
            # Fallback to keyword classification
            objection_type, confidence = self._classify_objection_keywords(objection_text)
            self.performance_metrics['fallback_uses'] += 1
            return objection_type, confidence, {'error': str(e), 'keyword_fallback': True}    
 
   # Private helper methods
    
    def _get_usage_tracker(self, lead_id: str, prospect_tier: ProspectTier) -> LLMUsageTracker:
        """Get or create usage tracker for lead."""
        if lead_id not in self.usage_trackers:
            self.usage_trackers[lead_id] = LLMUsageTracker(
                lead_id=lead_id,
                prospect_tier=prospect_tier
            )
        return self.usage_trackers[lead_id]
    
    def _generate_cache_key(self, usage_type: LLMUsageType, *args) -> str:
        """Generate cache key for LLM responses."""
        key_data = f"{usage_type.value}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _get_cached_response(self, cache_key: str, ttl_seconds: int) -> Optional[Dict[str, Any]]:
        """Get cached response if available and not expired."""
        try:
            if cache_key in self.cache:
                cached_data = self.cache[cache_key]
                created_at = datetime.fromisoformat(cached_data['created_at'])
                if (datetime.utcnow() - created_at).total_seconds() < ttl_seconds:
                    return cached_data
                else:
                    # Remove expired cache entry
                    del self.cache[cache_key]
        except Exception as e:
            logger.warning("Failed to get cached response", cache_key=cache_key, error=str(e))
        
        return None
    
    def _cache_response(self, cache_key: str, response_data: Dict[str, Any]) -> None:
        """Cache LLM response."""
        try:
            # Simple in-memory cache with size limit
            if len(self.cache) > 1000:  # Limit cache size
                # Remove oldest entries
                oldest_keys = sorted(
                    self.cache.keys(),
                    key=lambda k: self.cache[k]['created_at']
                )[:100]
                for key in oldest_keys:
                    del self.cache[key]
            
            self.cache[cache_key] = response_data
                
        except Exception as e:
            logger.warning("Failed to cache response", cache_key=cache_key, error=str(e))
    
    async def _check_daily_limits(self) -> bool:
        """Check if daily budget limits are exceeded."""
        await self._reset_daily_usage_if_needed()
        
        return (
            self.daily_usage.total_tokens < self.budget_limits.daily_token_limit and
            self.daily_usage.cost_estimate < self.budget_limits.daily_cost_limit
        )
    
    async def _reset_daily_usage_if_needed(self) -> None:
        """Reset daily usage if new day."""
        current_date = datetime.utcnow().date()
        if current_date > self.last_daily_reset:
            self.daily_usage = TokenUsage()
            self.last_daily_reset = current_date
            logger.info("Reset daily LLM usage tracking", date=current_date.isoformat())
    
    def _update_daily_usage(self, tokens_used: int, cost: float) -> None:
        """Update daily usage tracking."""
        self.daily_usage.total_tokens += tokens_used
        self.daily_usage.cost_estimate += cost
    
    def _estimate_cost(self, tokens_used: int) -> float:
        """Estimate cost based on token usage."""
        # Rough cost estimate for Claude-3.5-Sonnet
        # Input: ~$3/1M tokens, Output: ~$15/1M tokens
        # Assume 70% input, 30% output for estimation
        input_tokens = int(tokens_used * 0.7)
        output_tokens = int(tokens_used * 0.3)
        
        input_cost = (input_tokens / 1_000_000) * 3.0
        output_cost = (output_tokens / 1_000_000) * 15.0
        
        return input_cost + output_cost
    
    async def _generate_planner_response(self, prospect_data: Dict[str, Any], max_tokens: int) -> Tuple[str, int]:
        """Generate pre-call plan using base LLM service."""
        system_prompt = f"""Generate a concise pre-call plan for this prospect. Focus on:
1. Key talking points based on their profile
2. Potential objections and responses
3. Closing strategy
4. Next steps

Prospect Data: {json.dumps(prospect_data, indent=2)}

Keep the plan under {max_tokens} tokens and make it actionable."""
        
        try:
            response = await self.base_llm_service.client.chat.completions.create(
                model=self.base_llm_service.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': 'Generate the pre-call plan.'}
                ],
                max_tokens=max_tokens,
                temperature=0.3,  # Lower temperature for planning
                timeout=10.0
            )
            
            plan_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            return plan_text, tokens_used
            
        except Exception as e:
            logger.error("Failed to generate planner response", error=str(e))
            raise
    
    async def _generate_complex_objection_response(
        self, 
        objection_text: str, 
        context: Dict[str, Any], 
        max_tokens: int
    ) -> Tuple[str, int, bool]:
        """Generate response for complex objection."""
        system_prompt = f"""You are handling a complex sales objection. Provide a professional, empathetic response that:
1. Acknowledges the concern
2. Provides value-focused counter-arguments
3. Asks a follow-up question
4. Maintains conversation momentum

Objection: {objection_text}
Context: {json.dumps(context, indent=2)}

Respond in under {max_tokens} tokens. If the objection seems insurmountable, indicate escalation is needed."""
        
        try:
            response = await self.base_llm_service.client.chat.completions.create(
                model=self.base_llm_service.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'Handle this objection: {objection_text}'}
                ],
                max_tokens=max_tokens,
                temperature=0.5,
                timeout=10.0
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            # Simple heuristic to determine if escalation is needed
            should_escalate = any(phrase in response_text.lower() for phrase in [
                'escalate', 'transfer', 'human', 'specialist', 'manager'
            ])
            
            return response_text, tokens_used, should_escalate
            
        except Exception as e:
            logger.error("Failed to generate complex objection response", error=str(e))
            raise
    
    async def _generate_classification_response(
        self, 
        objection_text: str, 
        context: Dict[str, Any], 
        max_tokens: int
    ) -> Tuple[str, int]:
        """Generate objection classification."""
        system_prompt = f"""Classify this sales objection into one of these categories:
- price: Budget/cost concerns
- timing: Not the right time
- authority: Not the decision maker
- need: Don't see the need
- trust: Skeptical of solution/company
- competition: Already have a solution
- unknown: Cannot classify

Objection: {objection_text}
Context: {json.dumps(context or {}, indent=2)}

Respond with JSON: {{"objection_type": "category", "confidence": 0.0-1.0}}
Use exactly {max_tokens} tokens or less."""
        
        try:
            response = await self.base_llm_service.client.chat.completions.create(
                model=self.base_llm_service.model_name,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': f'Classify: {objection_text}'}
                ],
                max_tokens=max_tokens,
                temperature=0.1,  # Very low temperature for classification
                timeout=5.0
            )
            
            classification_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            return classification_text, tokens_used
            
        except Exception as e:
            logger.error("Failed to generate classification response", error=str(e))
            raise
    
    def _assess_objection_complexity(self, objection_text: str, context: Dict[str, Any]) -> float:
        """Assess objection complexity to determine if LLM is needed."""
        # Simple heuristics for complexity assessment
        complexity_score = 0.0
        
        objection_lower = objection_text.lower()
        
        # Length-based complexity
        if len(objection_text) > 100:
            complexity_score += 0.2
        
        # Multiple concerns in one objection
        concern_indicators = ['but', 'however', 'also', 'and', 'plus', 'additionally']
        concern_count = sum(1 for indicator in concern_indicators if indicator in objection_lower)
        complexity_score += min(0.3, concern_count * 0.1)
        
        # Emotional language
        emotional_words = ['frustrated', 'disappointed', 'concerned', 'worried', 'upset', 'angry']
        if any(word in objection_lower for word in emotional_words):
            complexity_score += 0.2
        
        # Technical or specific objections
        technical_indicators = ['integration', 'api', 'security', 'compliance', 'technical', 'system']
        if any(indicator in objection_lower for indicator in technical_indicators):
            complexity_score += 0.3
        
        # Context complexity
        if context:
            if context.get('conversation_history') and len(context['conversation_history']) > 10:
                complexity_score += 0.2
            if context.get('previous_objections'):
                complexity_score += 0.1
        
        return min(1.0, complexity_score)
    
    def _classify_objection_keywords(self, objection_text: str) -> Tuple[str, float]:
        """Simple keyword-based objection classification."""
        objection_lower = objection_text.lower()
        
        # Define keyword patterns for each objection type
        patterns = {
            'price': ['price', 'cost', 'expensive', 'budget', 'money', 'afford', 'cheap'],
            'timing': ['time', 'timing', 'busy', 'later', 'now', 'when', 'schedule'],
            'authority': ['boss', 'manager', 'decision', 'approval', 'team', 'committee'],
            'need': ['need', 'necessary', 'problem', 'working fine', 'satisfied'],
            'trust': ['trust', 'skeptical', 'doubt', 'unsure', 'risky', 'proven'],
            'competition': ['already have', 'current', 'existing', 'competitor', 'using']
        }
        
        # Score each category
        scores = {}
        for category, keywords in patterns.items():
            score = sum(1 for keyword in keywords if keyword in objection_lower)
            if score > 0:
                scores[category] = score / len(keywords)  # Normalize by keyword count
        
        if not scores:
            return 'unknown', 0.0
        
        # Return highest scoring category
        best_category = max(scores, key=scores.get)
        confidence = min(0.8, scores[best_category])  # Cap confidence for keyword matching
        
        return best_category, confidence
    
    def _get_template_objection_response(self, objection_text: str, context: Dict[str, Any]) -> Optional[str]:
        """Get template response for objection."""
        objection_type, _ = self._classify_objection_keywords(objection_text)
        
        return self.template_responses.get(objection_type, self.template_responses.get('unknown'))
    
    def _get_fallback_plan(self, prospect_data: Dict[str, Any]) -> str:
        """Get fallback pre-call plan when LLM fails."""
        company = prospect_data.get('company_name', 'the company')
        industry = prospect_data.get('industry', 'their industry')
        
        return f"""Pre-Call Plan for {company}:

1. Opening: Warm greeting and value proposition
2. Qualification: Understand their role and decision-making process
3. Needs Discovery: Identify pain points in {industry}
4. Solution Fit: Connect our capabilities to their needs
5. Objection Handling: Address budget, timing, or authority concerns
6. Next Steps: Schedule demo or follow-up meeting

Key Focus: Listen actively and build rapport throughout the conversation."""