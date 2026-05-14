"""
OpenRouter LLM Service for AI conversation generation and context management.
"""
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

import structlog
import openai
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.schemas.conversation import ConversationContext, ConversationRole
from app.utils.serialization import serialize_to_json, deserialize_from_json


logger = structlog.get_logger()


@dataclass
class TokenUsage:
    """Token usage tracking for LLM requests."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimate: float = 0.0
    
    def add_usage(self, usage_data: Dict[str, Any]) -> None:
        """Add usage data from API response."""
        self.prompt_tokens += usage_data.get('prompt_tokens', 0)
        self.completion_tokens += usage_data.get('completion_tokens', 0)
        self.total_tokens += usage_data.get('total_tokens', 0)
        
        # Estimate cost based on model pricing (rough estimates)
        # Claude-3.5-Sonnet: ~$3/1M input tokens, ~$15/1M output tokens
        input_cost = (usage_data.get('prompt_tokens', 0) / 1_000_000) * 3.0
        output_cost = (usage_data.get('completion_tokens', 0) / 1_000_000) * 15.0
        self.cost_estimate += input_cost + output_cost


@dataclass
class ConversationSession:
    """Conversation session with context management."""
    call_sid: str
    contact_context: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    extracted_information: Dict[str, Any] = field(default_factory=dict)
    lead_score: int = 0
    current_intent: Optional[str] = None
    buying_signals: List[str] = field(default_factory=list)
    objections: List[str] = field(default_factory=list)
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to conversation history."""
        self.conversation_history.append({
            'role': role,
            'content': content,
            'timestamp': datetime.utcnow().isoformat()
        })
        self.last_updated = datetime.utcnow()
        
        # Keep only last 20 messages to manage context window
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]
    
    def get_context_summary(self) -> str:
        """Generate a summary of the conversation context."""
        if not self.conversation_history:
            return "New conversation"
        
        message_count = len(self.conversation_history)
        duration = (self.last_updated - self.created_at).total_seconds() / 60
        
        return f"Conversation with {message_count} messages over {duration:.1f} minutes"


class OpenRouterLLMService:
    """Service for OpenRouter LLM integration with conversation management."""
    
    def __init__(self):
        """Initialize OpenRouter LLM service."""
        self.settings = get_settings()
        
        # Initialize OpenAI client configured for OpenRouter
        self.client = AsyncOpenAI(
            api_key=self.settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Model configuration
        self.model_name = self.settings.OPENROUTER_MODEL
        self.max_tokens = 150  # Optimized for phone conversations
        self.temperature = 0.7  # Balanced creativity and consistency
        
        # Active conversation sessions
        self.active_sessions: Dict[str, ConversationSession] = {}
        
        # Token usage tracking
        self.total_usage = TokenUsage()
        self.daily_usage = TokenUsage()
        self.last_reset = datetime.utcnow().date()
        
        # Response validation patterns
        self.safety_filters = [
            r'(?i)\b(credit card|ssn|social security|password|pin)\b',
            r'(?i)\b(illegal|harmful|dangerous)\b',
            r'(?i)\b(hate|discrimination|violence)\b'
        ]
        
        # Conversation optimization settings
        self.context_window_limit = 4000  # Tokens
        self.response_timeout = 10.0  # Seconds
        
    async def generate_response(
        self,
        call_sid: str,
        user_input: str,
        contact_context: Optional[Dict[str, Any]] = None,
        conversation_context: Optional[ConversationContext] = None
    ) -> Tuple[str, int, Dict[str, Any]]:
        """
        Generate AI response for conversation turn.
        
        Args:
            call_sid: Twilio Call SID
            user_input: User's message
            contact_context: Salesforce contact information
            conversation_context: Current conversation context
            
        Returns:
            Tuple of (response_text, tokens_used, analysis_data)
        """
        start_time = time.time()
        
        try:
            # Get or create conversation session
            session = await self._get_or_create_session(
                call_sid, contact_context, conversation_context
            )
            
            # Add user message to session
            session.add_message('user', user_input)
            
            # Build dynamic prompt with context
            system_prompt = await self._build_system_prompt(session)
            messages = await self._build_message_history(session)
            
            # Generate response with safety validation
            response_text, tokens_used = await self._generate_llm_response(
                system_prompt, messages, user_input
            )
            
            # Validate and filter response
            validated_response = await self._validate_response(response_text)
            
            # Add AI response to session
            session.add_message('assistant', validated_response)
            
            # Analyze conversation for insights
            analysis_data = await self._analyze_conversation_turn(
                session, user_input, validated_response
            )
            
            # Update session with analysis
            await self._update_session_analysis(session, analysis_data)
            
            # Update token usage tracking
            session.token_usage.add_usage({'total_tokens': tokens_used})
            self._update_usage_tracking(tokens_used)
            
            processing_time = (time.time() - start_time) * 1000
            
            logger.info(
                "Generated LLM response",
                call_sid=call_sid,
                user_input_length=len(user_input),
                response_length=len(validated_response),
                tokens_used=tokens_used,
                processing_time_ms=processing_time,
                lead_score=session.lead_score,
                current_intent=session.current_intent
            )
            
            return validated_response, tokens_used, analysis_data
            
        except Exception as e:
            logger.error(
                "Failed to generate LLM response",
                call_sid=call_sid,
                user_input=user_input[:100] if user_input else None,
                error=str(e),
                error_type=type(e).__name__
            )
            
            # Return fallback response
            fallback_response = await self._get_fallback_response(user_input)
            return fallback_response, 0, {'error': str(e)}
    
    async def analyze_conversation_intent(
        self,
        call_sid: str,
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Analyze conversation to determine intent and extract insights.
        
        Args:
            call_sid: Twilio Call SID
            conversation_history: List of conversation messages
            
        Returns:
            Dictionary with intent analysis results
        """
        try:
            session = self.active_sessions.get(call_sid)
            if not session:
                logger.warning("No active session for intent analysis", call_sid=call_sid)
                return {'intent': 'unknown', 'confidence': 0.0}
            
            # Build analysis prompt
            analysis_prompt = self._build_intent_analysis_prompt(conversation_history)
            
            # Generate analysis
            messages = [
                {'role': 'system', 'content': analysis_prompt},
                {'role': 'user', 'content': 'Analyze the conversation intent and provide structured output.'}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=200,
                temperature=0.3,  # Lower temperature for analysis
                timeout=self.response_timeout
            )
            
            # Parse structured response
            analysis_text = response.choices[0].message.content
            analysis_data = await self._parse_intent_analysis(analysis_text)
            
            # Update session with analysis
            if session:
                session.current_intent = analysis_data.get('intent')
                session.buying_signals.extend(analysis_data.get('buying_signals', []))
                session.objections.extend(analysis_data.get('objections', []))
            
            logger.info(
                "Analyzed conversation intent",
                call_sid=call_sid,
                intent=analysis_data.get('intent'),
                confidence=analysis_data.get('confidence'),
                buying_signals=len(analysis_data.get('buying_signals', []))
            )
            
            return analysis_data
            
        except Exception as e:
            logger.error(
                "Failed to analyze conversation intent",
                call_sid=call_sid,
                error=str(e)
            )
            return {'intent': 'unknown', 'confidence': 0.0, 'error': str(e)}
    
    async def calculate_lead_score(
        self,
        call_sid: str,
        conversation_context: ConversationContext
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Calculate lead qualification score based on conversation.
        
        Args:
            call_sid: Twilio Call SID
            conversation_context: Current conversation context
            
        Returns:
            Tuple of (lead_score, scoring_rationale)
        """
        try:
            session = self.active_sessions.get(call_sid)
            if not session:
                return 0, {'error': 'No active session'}
            
            # Build scoring prompt
            scoring_prompt = self._build_lead_scoring_prompt(session)
            
            messages = [
                {'role': 'system', 'content': scoring_prompt},
                {'role': 'user', 'content': 'Calculate lead score and provide rationale.'}
            ]
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=300,
                temperature=0.2,  # Very low temperature for scoring consistency
                timeout=self.response_timeout
            )
            
            # Parse scoring response
            scoring_text = response.choices[0].message.content
            score_data = await self._parse_lead_scoring(scoring_text)
            
            lead_score = score_data.get('score', 0)
            rationale = score_data.get('rationale', {})
            
            # Update session
            session.lead_score = lead_score
            
            logger.info(
                "Calculated lead score",
                call_sid=call_sid,
                lead_score=lead_score,
                rationale_factors=len(rationale)
            )
            
            return lead_score, rationale
            
        except Exception as e:
            logger.error(
                "Failed to calculate lead score",
                call_sid=call_sid,
                error=str(e)
            )
            return 0, {'error': str(e)}
    
    async def get_conversation_summary(
        self,
        call_sid: str
    ) -> Dict[str, Any]:
        """
        Generate comprehensive conversation summary.
        
        Args:
            call_sid: Twilio Call SID
            
        Returns:
            Dictionary with conversation summary
        """
        try:
            session = self.active_sessions.get(call_sid)
            if not session:
                return {'error': 'No active session found'}
            
            summary_data = {
                'call_sid': call_sid,
                'duration_minutes': (session.last_updated - session.created_at).total_seconds() / 60,
                'message_count': len(session.conversation_history),
                'lead_score': session.lead_score,
                'current_intent': session.current_intent,
                'buying_signals': session.buying_signals,
                'objections': session.objections,
                'extracted_information': session.extracted_information,
                'token_usage': {
                    'total_tokens': session.token_usage.total_tokens,
                    'cost_estimate': session.token_usage.cost_estimate
                },
                'context_summary': session.get_context_summary()
            }
            
            logger.info(
                "Generated conversation summary",
                call_sid=call_sid,
                duration_minutes=summary_data['duration_minutes'],
                lead_score=summary_data['lead_score']
            )
            
            return summary_data
            
        except Exception as e:
            logger.error(
                "Failed to generate conversation summary",
                call_sid=call_sid,
                error=str(e)
            )
            return {'error': str(e)}
    
    async def cleanup_session(self, call_sid: str) -> None:
        """
        Clean up conversation session and resources.
        
        Args:
            call_sid: Twilio Call SID
        """
        try:
            session = self.active_sessions.pop(call_sid, None)
            if session:
                # Log final session stats
                logger.info(
                    "Cleaned up LLM session",
                    call_sid=call_sid,
                    duration_minutes=(session.last_updated - session.created_at).total_seconds() / 60,
                    total_tokens=session.token_usage.total_tokens,
                    final_lead_score=session.lead_score
                )
            
        except Exception as e:
            logger.error(
                "Failed to cleanup LLM session",
                call_sid=call_sid,
                error=str(e)
            )
    
    async def get_token_usage_stats(self) -> Dict[str, Any]:
        """
        Get current token usage statistics.
        
        Returns:
            Dictionary with usage statistics
        """
        try:
            # Reset daily usage if needed
            current_date = datetime.utcnow().date()
            if current_date > self.last_reset:
                self.daily_usage = TokenUsage()
                self.last_reset = current_date
            
            return {
                'daily_usage': {
                    'total_tokens': self.daily_usage.total_tokens,
                    'cost_estimate': self.daily_usage.cost_estimate,
                    'reset_date': self.last_reset.isoformat()
                },
                'total_usage': {
                    'total_tokens': self.total_usage.total_tokens,
                    'cost_estimate': self.total_usage.cost_estimate
                },
                'active_sessions': len(self.active_sessions),
                'model_name': self.model_name,
                'last_updated': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Failed to get token usage stats", error=str(e))
            return {'error': str(e)}
    
    async def _get_or_create_session(
        self,
        call_sid: str,
        contact_context: Optional[Dict[str, Any]],
        conversation_context: Optional[ConversationContext]
    ) -> ConversationSession:
        """Get existing session or create new one."""
        if call_sid in self.active_sessions:
            session = self.active_sessions[call_sid]
            # Update contact context if provided
            if contact_context:
                session.contact_context.update(contact_context)
            return session
        
        # Create new session
        session = ConversationSession(
            call_sid=call_sid,
            contact_context=contact_context or {},
            extracted_information=conversation_context.extracted_information if conversation_context else {}
        )
        
        # Import existing conversation history if available
        if conversation_context and conversation_context.turns:
            for turn in conversation_context.turns[-10:]:  # Last 10 turns
                session.add_message(turn.role.value, turn.content)
        
        self.active_sessions[call_sid] = session
        return session
    
    async def _build_system_prompt(self, session: ConversationSession) -> str:
        """Build dynamic system prompt with context."""
        base_prompt = """You are a professional AI sales assistant handling inbound calls for a business. Your goal is to:

1. Provide helpful information about services
2. Qualify leads by understanding their needs
3. Gather contact information naturally
4. Maintain a professional, friendly tone
5. Keep responses concise (1-2 sentences max for phone calls)

IMPORTANT GUIDELINES:
- Keep responses under 150 tokens for phone conversation flow
- Ask one question at a time
- Be conversational and natural
- Focus on understanding the caller's needs
- Identify buying signals (budget, timeline, decision authority)
- Handle objections professionally
- Never ask for sensitive information like credit cards or SSNs

"""
        
        # Add contact context if available
        if session.contact_context:
            contact_info = []
            if session.contact_context.get('Name'):
                contact_info.append(f"Caller name: {session.contact_context['Name']}")
            if session.contact_context.get('Company'):
                contact_info.append(f"Company: {session.contact_context['Company']}")
            if session.contact_context.get('Industry'):
                contact_info.append(f"Industry: {session.contact_context['Industry']}")
            
            if contact_info:
                base_prompt += f"\nCONTACT CONTEXT:\n{chr(10).join(contact_info)}\n"
        
        # Add conversation insights
        if session.current_intent:
            base_prompt += f"\nCURRENT INTENT: {session.current_intent}\n"
        
        if session.buying_signals:
            base_prompt += f"\nBUYING SIGNALS DETECTED: {', '.join(session.buying_signals[-3:])}\n"
        
        if session.objections:
            base_prompt += f"\nOBJECTIONS TO ADDRESS: {', '.join(session.objections[-2:])}\n"
        
        return base_prompt
    
    async def _build_message_history(self, session: ConversationSession) -> List[Dict[str, str]]:
        """Build message history for LLM context."""
        messages = []
        
        # Include recent conversation history (last 10 messages)
        recent_history = session.conversation_history[-10:]
        
        for msg in recent_history:
            messages.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        return messages
    
    async def _generate_llm_response(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        user_input: str
    ) -> Tuple[str, int]:
        """Generate response using OpenRouter LLM."""
        try:
            # Build complete message list
            full_messages = [{'role': 'system', 'content': system_prompt}]
            full_messages.extend(messages)
            full_messages.append({'role': 'user', 'content': user_input})
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=full_messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=self.response_timeout
            )
            
            response_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            return response_text, tokens_used
            
        except Exception as e:
            logger.error("LLM generation failed", error=str(e))
            raise
    
    async def _validate_response(self, response: str) -> str:
        """Validate and filter AI response for safety."""
        import re
        
        # Check for safety violations
        for pattern in self.safety_filters:
            if re.search(pattern, response):
                logger.warning("Safety filter triggered", pattern=pattern)
                return "I apologize, but I need to keep our conversation focused on how I can help you with our services. What specific information are you looking for?"
        
        # Ensure response length is appropriate for phone calls
        if len(response) > 500:  # Too long for phone conversation
            sentences = response.split('. ')
            response = '. '.join(sentences[:2]) + '.'
        
        return response.strip()
    
    async def _analyze_conversation_turn(
        self,
        session: ConversationSession,
        user_input: str,
        ai_response: str
    ) -> Dict[str, Any]:
        """Analyze conversation turn for insights."""
        analysis = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_input_length': len(user_input),
            'ai_response_length': len(ai_response),
            'detected_signals': [],
            'extracted_info': {}
        }
        
        # Simple keyword-based analysis
        user_lower = user_input.lower()
        
        # Buying signals
        buying_keywords = ['budget', 'price', 'cost', 'buy', 'purchase', 'timeline', 'when', 'decision']
        for keyword in buying_keywords:
            if keyword in user_lower:
                analysis['detected_signals'].append(f'buying_signal_{keyword}')
        
        # Contact information extraction
        import re
        
        # Email detection
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, user_input)
        if emails:
            analysis['extracted_info']['email'] = emails[0]
        
        # Company name detection (simple heuristic)
        company_indicators = ['company', 'work at', 'from', 'business']
        for indicator in company_indicators:
            if indicator in user_lower:
                # Extract potential company name (simplified)
                words = user_input.split()
                try:
                    idx = next(i for i, word in enumerate(words) if indicator in word.lower())
                    if idx + 1 < len(words):
                        analysis['extracted_info']['company_mention'] = words[idx + 1]
                except StopIteration:
                    pass
        
        return analysis
    
    async def _update_session_analysis(
        self,
        session: ConversationSession,
        analysis_data: Dict[str, Any]
    ) -> None:
        """Update session with analysis insights."""
        # Update extracted information
        if 'extracted_info' in analysis_data:
            session.extracted_information.update(analysis_data['extracted_info'])
        
        # Update buying signals
        for signal in analysis_data.get('detected_signals', []):
            if signal.startswith('buying_signal_') and signal not in session.buying_signals:
                session.buying_signals.append(signal.replace('buying_signal_', ''))
        
        # Update lead score based on signals
        signal_count = len(analysis_data.get('detected_signals', []))
        if signal_count > 0:
            session.lead_score = min(100, session.lead_score + (signal_count * 10))
    
    def _build_intent_analysis_prompt(self, conversation_history: List[Dict[str, str]]) -> str:
        """Build prompt for intent analysis."""
        return f"""Analyze this conversation to determine the caller's primary intent and extract insights.

Conversation History:
{json.dumps(conversation_history, indent=2)}

Provide analysis in this format:
Intent: [information_seeking|lead_qualification|support_request|sales_inquiry|other]
Confidence: [0.0-1.0]
Buying Signals: [list of detected buying signals]
Objections: [list of objections raised]
Key Topics: [main topics discussed]

Keep analysis concise and factual."""
    
    def _build_lead_scoring_prompt(self, session: ConversationSession) -> str:
        """Build prompt for lead scoring."""
        return f"""Score this lead based on the conversation and context (0-100 scale).

Contact Context: {json.dumps(session.contact_context)}
Conversation History: {json.dumps(session.conversation_history[-5:])}
Buying Signals: {session.buying_signals}
Extracted Information: {json.dumps(session.extracted_information)}

Scoring Criteria:
- Budget mentioned: +20 points
- Timeline discussed: +15 points
- Decision authority: +15 points
- Specific needs identified: +10 points
- Contact information provided: +10 points
- Company size/industry fit: +10 points
- Engagement level: +10 points
- Objections handled: +5 points

Provide:
Score: [0-100]
Rationale: [key factors that influenced the score]"""
    
    async def _parse_intent_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse structured intent analysis response."""
        try:
            lines = analysis_text.strip().split('\n')
            result = {
                'intent': 'unknown',
                'confidence': 0.0,
                'buying_signals': [],
                'objections': [],
                'key_topics': []
            }
            
            for line in lines:
                if line.startswith('Intent:'):
                    result['intent'] = line.split(':', 1)[1].strip()
                elif line.startswith('Confidence:'):
                    try:
                        result['confidence'] = float(line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith('Buying Signals:'):
                    signals = line.split(':', 1)[1].strip()
                    if signals and signals != '[]':
                        result['buying_signals'] = [s.strip() for s in signals.split(',')]
                elif line.startswith('Objections:'):
                    objections = line.split(':', 1)[1].strip()
                    if objections and objections != '[]':
                        result['objections'] = [o.strip() for o in objections.split(',')]
                elif line.startswith('Key Topics:'):
                    topics = line.split(':', 1)[1].strip()
                    if topics and topics != '[]':
                        result['key_topics'] = [t.strip() for t in topics.split(',')]
            
            return result
            
        except Exception as e:
            logger.error("Failed to parse intent analysis", error=str(e))
            return {'intent': 'unknown', 'confidence': 0.0}
    
    async def _parse_lead_scoring(self, scoring_text: str) -> Dict[str, Any]:
        """Parse structured lead scoring response."""
        try:
            lines = scoring_text.strip().split('\n')
            result = {
                'score': 0,
                'rationale': {}
            }
            
            for line in lines:
                if line.startswith('Score:'):
                    try:
                        result['score'] = int(line.split(':', 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith('Rationale:'):
                    result['rationale']['explanation'] = line.split(':', 1)[1].strip()
            
            return result
            
        except Exception as e:
            logger.error("Failed to parse lead scoring", error=str(e))
            return {'score': 0, 'rationale': {'error': str(e)}}
    
    async def _get_fallback_response(self, user_input: str) -> str:
        """Get fallback response when LLM fails."""
        fallback_responses = [
            "I apologize, but I'm having a technical issue. Could you please repeat that?",
            "I'm sorry, I didn't catch that clearly. Could you tell me more about what you're looking for?",
            "Let me make sure I understand correctly. Could you rephrase that for me?",
            "I want to make sure I give you the right information. Could you tell me more about your needs?"
        ]
        
        # Simple selection based on input length
        if len(user_input) < 10:
            return fallback_responses[0]
        elif 'help' in user_input.lower():
            return fallback_responses[1]
        else:
            return fallback_responses[2]
    
    def _update_usage_tracking(self, tokens_used: int) -> None:
        """Update token usage tracking."""
        self.total_usage.total_tokens += tokens_used
        self.daily_usage.total_tokens += tokens_used
        
        # Rough cost estimation (will be more accurate with actual API response)
        cost_per_token = 0.000015  # Rough estimate for Claude-3.5-Sonnet
        cost = tokens_used * cost_per_token
        
        self.total_usage.cost_estimate += cost
        self.daily_usage.cost_estimate += cost


# Global instance
openrouter_llm_service = OpenRouterLLMService()