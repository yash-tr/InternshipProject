"""
FSM-Based Dialog Management Service

This module implements a finite state machine for managing conversation flow
in the AI Calling Agent MVP. It provides template-first responses with selective
LLM usage, following strict budget controls and cost optimization principles.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field
import json
import hashlib

from statemachine import StateMachine, State, Event
from pydantic import BaseModel, Field

from ..core.config import get_settings
from ..schemas.conversation import ConversationContext, ConversationRole
from ..services.openrouter_llm import openrouter_llm_service
from ..services.objection_handler import enhanced_objection_handler
from ..utils.encryption import encrypt_pii_data, decrypt_pii_data

logger = logging.getLogger(__name__)
settings = get_settings()


class DialogState(str, Enum):
    """Dialog states for conversation flow."""
    GREETING = "greeting"
    QUALIFICATION = "qualification"
    NEEDS_ANALYSIS = "needs_analysis"
    OBJECTION_HANDLING = "objection_handling"
    CLOSING = "closing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    TRANSFERRED = "transferred"


class DialogEvent(str, Enum):
    """Dialog events for state transitions."""
    START_CONVERSATION = "start_conversation"
    QUALIFY_PROSPECT = "qualify_prospect"
    ANALYZE_NEEDS = "analyze_needs"
    HANDLE_OBJECTION = "handle_objection"
    ATTEMPT_CLOSE = "attempt_close"
    COMPLETE_CALL = "complete_call"
    ABANDON_CALL = "abandon_call"
    TRANSFER_HUMAN = "transfer_human"
    TIMEOUT = "timeout"


@dataclass
class DialogTemplate:
    """Template for dialog responses."""
    template_id: str
    state: DialogState
    trigger: str  # What triggers this template
    response: str
    follow_up_questions: List[str] = field(default_factory=list)
    next_state: Optional[DialogState] = None
    conditions: List[str] = field(default_factory=list)
    priority: int = 1  # Higher priority templates are preferred
@datacla
ss
class LLMBudgetTracker:
    """Tracks LLM usage for budget control."""
    max_llm_calls_non_vip: int = 1
    max_llm_calls_vip: int = 3
    max_tokens_per_call: int = 80
    current_llm_calls: int = 0
    current_tokens_used: int = 0
    is_vip: bool = False
    
    def can_use_llm(self) -> bool:
        """Check if LLM usage is within budget."""
        max_calls = self.max_llm_calls_vip if self.is_vip else self.max_llm_calls_non_vip
        return self.current_llm_calls < max_calls
    
    def record_llm_usage(self, tokens_used: int):
        """Record LLM usage."""
        self.current_llm_calls += 1
        self.current_tokens_used += tokens_used


@dataclass
class DialogContext:
    """Context for dialog management."""
    call_sid: str
    prospect_data: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    extracted_information: Dict[str, Any]
    current_state: DialogState
    state_entry_time: datetime
    timeout_duration: timedelta = timedelta(minutes=2)
    llm_budget: LLMBudgetTracker = field(default_factory=LLMBudgetTracker)
    objections_handled: List[str] = field(default_factory=list)
    closing_attempts: int = 0
    
    def is_timeout(self) -> bool:
        """Check if current state has timed out."""
        return datetime.utcnow() - self.state_entry_time > self.timeout_duration
    
    def reset_state_timer(self):
        """Reset the state entry time."""
        self.state_entry_time = datetime.utcnow()


class DialogTemplateLibrary:
    """Library of pre-built dialog templates."""
    
    def __init__(self):
        self.templates: Dict[str, List[DialogTemplate]] = {}
        self._initialize_templates()
    
    def _initialize_templates(self):
        """Initialize the template library with pre-built responses."""
        # Greeting templates
        self.add_template(DialogTemplate(
            template_id="greeting_professional",
            state=DialogState.GREETING,
            trigger="call_start",
            response="Hello! Thank you for taking my call. I'm an AI assistant calling on behalf of our sales team. I hope I'm not catching you at a bad time?",
            follow_up_questions=["How are you doing today?"],
            next_state=DialogState.QUALIFICATION,
            priority=1
        ))
        
        self.add_template(DialogTemplate(
            template_id="greeting_warm",
            state=DialogState.GREETING,
            trigger="call_start_warm",
            response="Hi there! This is an AI assistant from our sales team. I was hoping to have a quick conversation with you about your business needs. Do you have a couple of minutes?",
            follow_up_questions=["Is now a good time to chat?"],
            next_state=DialogState.QUALIFICATION,
            priority=2
        ))
        
        # Qualification templates
        self.add_template(DialogTemplate(
            template_id="qualification_role",
            state=DialogState.QUALIFICATION,
            trigger="ask_role",
            response="Great! To make sure I'm speaking with the right person, could you tell me a bit about your role at the company?",
            follow_up_questions=["What's your position?", "Are you involved in technology decisions?"],
            next_state=DialogState.NEEDS_ANALYSIS,
            priority=1
        ))
        
        self.add_template(DialogTemplate(
            template_id="qualification_company_size",
            state=DialogState.QUALIFICATION,
            trigger="ask_company_size",
            response="That's helpful to know. Can you give me a sense of your company size? How many employees do you have approximately?",
            follow_up_questions=["What industry are you in?"],
            next_state=DialogState.NEEDS_ANALYSIS,
            priority=1
        ))
        
        # Needs analysis templates
        self.add_template(DialogTemplate(
            template_id="needs_pain_points",
            state=DialogState.NEEDS_ANALYSIS,
            trigger="identify_pain_points",
            response="I'd love to understand your current challenges better. What are some of the biggest pain points you're facing in your day-to-day operations?",
            follow_up_questions=["How are you handling that currently?", "What would an ideal solution look like?"],
            next_state=DialogState.CLOSING,
            priority=1
        ))
        
        # Objection handling templates
        self.add_template(DialogTemplate(
            template_id="objection_price",
            state=DialogState.OBJECTION_HANDLING,
            trigger="price_objection",
            response="I understand cost is always a consideration. Let me ask you this - what's the cost of not solving this problem? How much time and money are you losing with your current situation?",
            follow_up_questions=["What's your budget range for solving this?"],
            next_state=DialogState.CLOSING,
            priority=1
        ))
        
        self.add_template(DialogTemplate(
            template_id="objection_timing",
            state=DialogState.OBJECTION_HANDLING,
            trigger="timing_objection",
            response="I completely understand timing is important. The good news is we can work with your timeline. What would be the ideal timeframe for you to see results?",
            follow_up_questions=["What's driving the urgency?", "When would you like to start seeing improvements?"],
            next_state=DialogState.CLOSING,
            priority=1
        ))
        
        # Closing templates
        self.add_template(DialogTemplate(
            template_id="closing_soft",
            state=DialogState.CLOSING,
            trigger="soft_close",
            response="Based on what you've shared, it sounds like our solution could really help address those challenges. Would you be interested in seeing a quick demo of how this could work for your specific situation?",
            follow_up_questions=["When would be a good time for a 15-minute demo?"],
            next_state=DialogState.COMPLETED,
            priority=1
        ))
        
        self.add_template(DialogTemplate(
            template_id="closing_assumptive",
            state=DialogState.CLOSING,
            trigger="assumptive_close",
            response="Perfect! It sounds like this is exactly what you need. I'd love to get you set up with a trial so you can see the results firsthand. Should we schedule a quick implementation call for next week?",
            follow_up_questions=["What day works best for you?"],
            next_state=DialogState.COMPLETED,
            priority=2
        ))
        
        # Completion templates
        self.add_template(DialogTemplate(
            template_id="completion_success",
            state=DialogState.COMPLETED,
            trigger="call_success",
            response="Excellent! I'll have someone from our team reach out to you within the next business day to get everything set up. Thank you so much for your time today!",
            follow_up_questions=[],
            next_state=None,
            priority=1
        ))
        
        # Abandonment templates
        self.add_template(DialogTemplate(
            template_id="abandonment_polite",
            state=DialogState.ABANDONED,
            trigger="call_abandon",
            response="I understand this might not be the right time. Thank you for your time, and please don't hesitate to reach out if your situation changes. Have a great day!",
            follow_up_questions=[],
            next_state=None,
            priority=1
        ))
    
    def add_template(self, template: DialogTemplate):
        """Add a template to the library."""
        if template.state.value not in self.templates:
            self.templates[template.state.value] = []
        self.templates[template.state.value].append(template)
    
    def get_templates(self, state: DialogState, trigger: str = None) -> List[DialogTemplate]:
        """Get templates for a specific state and trigger."""
        state_templates = self.templates.get(state.value, [])
        
        if trigger:
            # Filter by trigger and sort by priority
            matching_templates = [t for t in state_templates if t.trigger == trigger]
            return sorted(matching_templates, key=lambda x: x.priority, reverse=True)
        
        return sorted(state_templates, key=lambda x: x.priority, reverse=True)
    
    def find_best_template(self, state: DialogState, context: DialogContext, user_input: str = None) -> Optional[DialogTemplate]:
        """Find the best template for the current context."""
        state_templates = self.templates.get(state.value, [])
        
        if not state_templates:
            return None
        
        # Simple keyword matching for now - could be enhanced with ML
        if user_input:
            user_input_lower = user_input.lower()
            
            # Check for specific triggers based on user input
            if any(word in user_input_lower for word in ['price', 'cost', 'expensive', 'budget']):
                templates = self.get_templates(state, 'price_objection')
                if templates:
                    return templates[0]
            
            if any(word in user_input_lower for word in ['time', 'busy', 'later', 'timing']):
                templates = self.get_templates(state, 'timing_objection')
                if templates:
                    return templates[0]
        
        # Return the highest priority template for the state
        return sorted(state_templates, key=lambda x: x.priority, reverse=True)[0]
class
 ConversationStateMachine(StateMachine):
    """
    Finite State Machine for managing conversation flow.
    
    Implements template-first responses with selective LLM usage,
    following strict budget controls and timeout handling.
    """
    
    # Define states
    greeting = State(DialogState.GREETING.value, initial=True)
    qualification = State(DialogState.QUALIFICATION.value)
    needs_analysis = State(DialogState.NEEDS_ANALYSIS.value)
    objection_handling = State(DialogState.OBJECTION_HANDLING.value)
    closing = State(DialogState.CLOSING.value)
    completed = State(DialogState.COMPLETED.value, final=True)
    abandoned = State(DialogState.ABANDONED.value, final=True)
    transferred = State(DialogState.TRANSFERRED.value, final=True)
    
    # Define events/transitions
    start_conversation = Event(greeting.to(qualification))
    qualify_prospect = Event(qualification.to(needs_analysis))
    analyze_needs = Event(needs_analysis.to(closing) | needs_analysis.to(objection_handling))
    handle_objection = Event(objection_handling.to(closing) | objection_handling.to(abandoned))
    attempt_close = Event(closing.to(completed) | closing.to(objection_handling))
    complete_call = Event(completed.from_(closing, needs_analysis))
    abandon_call = Event(abandoned.from_(greeting, qualification, needs_analysis, objection_handling, closing))
    transfer_human = Event(transferred.from_(greeting, qualification, needs_analysis, objection_handling, closing))
    timeout = Event(abandoned.from_(greeting, qualification, needs_analysis, objection_handling, closing))
    
    def __init__(self, context: DialogContext, template_library: DialogTemplateLibrary):
        self.context = context
        self.template_library = template_library
        self.llm_cache: Dict[str, str] = {}  # Simple in-memory cache
        super().__init__()
    
    async def process_user_input(self, user_input: str) -> Tuple[str, bool]:
        """
        Process user input and generate appropriate response.
        
        Args:
            user_input: User's speech input
            
        Returns:
            Tuple of (response_text, should_end_call)
        """
        try:
            # Check for timeout
            if self.context.is_timeout():
                logger.warning(f"Dialog timeout in state {self.current_state.id}")
                await self.timeout()
                return "I notice we've been quiet for a while. Thank you for your time, and have a great day!", True
            
            # Reset state timer
            self.context.reset_state_timer()
            
            # Update conversation history
            self.context.conversation_history.append({
                'role': 'user',
                'content': user_input,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Determine response using template-first approach
            response_text, should_end = await self._generate_response(user_input)
            
            # Update conversation history with response
            self.context.conversation_history.append({
                'role': 'assistant',
                'content': response_text,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return response_text, should_end
            
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return "I'm sorry, I'm having some technical difficulties. Let me transfer you to a human representative.", True
    
    async def _generate_response(self, user_input: str) -> Tuple[str, bool]:
        """Generate response using template-first approach with objection handling and LLM fallback."""
        current_state = DialogState(self.current_state.id)
        
        # First, check if this is an objection that needs special handling
        objection_response, should_escalate = await self._handle_potential_objection(user_input, current_state)
        if objection_response:
            # If escalation is needed, transition to transferred state
            if should_escalate:
                await self._transition_to_state(DialogState.TRANSFERRED)
                return objection_response, True
            
            # If objection was handled, potentially transition to objection handling state
            if current_state != DialogState.OBJECTION_HANDLING:
                await self._transition_to_state(DialogState.OBJECTION_HANDLING)
            
            return objection_response, False
        
        # Try template-first approach for non-objections
        template = self.template_library.find_best_template(current_state, self.context, user_input)
        
        if template:
            response = template.response
            
            # Handle state transitions
            if template.next_state:
                await self._transition_to_state(template.next_state)
            
            # Check if call should end
            should_end = current_state in [DialogState.COMPLETED, DialogState.ABANDONED, DialogState.TRANSFERRED]
            
            logger.info(f"Used template {template.template_id} for state {current_state.value}")
            return response, should_end
        
        # Fallback to LLM if template not found and budget allows
        if self.context.llm_budget.can_use_llm():
            try:
                response = await self._generate_llm_response(user_input, current_state)
                
                # Determine next state based on LLM response analysis
                next_state = await self._analyze_response_for_state_transition(response, user_input)
                if next_state:
                    await self._transition_to_state(next_state)
                
                should_end = current_state in [DialogState.COMPLETED, DialogState.ABANDONED, DialogState.TRANSFERRED]
                return response, should_end
                
            except Exception as e:
                logger.error(f"LLM response generation failed: {e}")
        
        # Final fallback to generic response
        return await self._get_fallback_response(current_state, user_input)
    
    async def _handle_potential_objection(self, user_input: str, current_state: DialogState) -> Tuple[Optional[str], bool]:
        """
        Handle potential objections using the enhanced objection handler.
        
        Args:
            user_input: User's input that might be an objection
            current_state: Current dialog state
            
        Returns:
            Tuple of (response_text, should_escalate) or (None, False) if not an objection
        """
        try:
            # Check if this looks like an objection using simple heuristics first
            if not self._looks_like_objection(user_input):
                return None, False
            
            # Use enhanced objection handler
            response_text, should_escalate, objection_info = await enhanced_objection_handler.handle_objection(
                call_sid=self.context.call_sid,
                user_input=user_input,
                prospect_data=self.context.prospect_data,
                conversation_context={
                    "current_state": current_state.value,
                    "conversation_history": self.context.conversation_history,
                    "objections_handled": self.context.objections_handled
                }
            )
            
            # Track objection in context
            self.context.objections_handled.append(objection_info.get("objection_type", "unknown"))
            
            logger.info(f"Handled objection: {objection_info.get('objection_type')} (confidence: {objection_info.get('confidence', 0):.2f})")
            
            return response_text, should_escalate
            
        except Exception as e:
            logger.error(f"Error handling potential objection: {e}")
            return None, False
    
    def _looks_like_objection(self, user_input: str) -> bool:
        """Simple heuristic to check if input looks like an objection."""
        if not user_input:
            return False
        
        user_input_lower = user_input.lower()
        
        # Common objection indicators
        objection_indicators = [
            # Price objections
            "expensive", "cost", "price", "budget", "afford", "money",
            # Timing objections
            "time", "busy", "later", "now", "timing",
            # Authority objections
            "boss", "manager", "decision", "approval", "team",
            # Need objections
            "need", "don't need", "working fine", "satisfied",
            # Trust objections
            "trust", "skeptical", "doubt", "unsure", "risky",
            # Competition objections
            "already have", "current", "existing", "competitor",
            # General objection words
            "but", "however", "concern", "worried", "problem", "issue",
            "not interested", "not sure", "don't think"
        ]
        
        return any(indicator in user_input_lower for indicator in objection_indicators)
    
    async def _generate_llm_response(self, user_input: str, current_state: DialogState) -> str:
        """Generate response using LLM with strict budget controls."""
        # Create cache key
        cache_key = hashlib.md5(f"{current_state.value}:{user_input}".encode()).hexdigest()
        
        # Check cache first
        if cache_key in self.llm_cache:
            logger.info("Using cached LLM response")
            return self.llm_cache[cache_key]
        
        # Build context-aware prompt
        system_prompt = self._build_system_prompt(current_state)
        conversation_context = self._build_conversation_context()
        
        try:
            # Generate response with token limits
            response, tokens_used, _ = await openrouter_llm_service.generate_response(
                call_sid=self.context.call_sid,
                user_input=user_input,
                contact_context=self.context.prospect_data,
                conversation_context=conversation_context,
                system_prompt=system_prompt,
                max_tokens=self.context.llm_budget.max_tokens_per_call
            )
            
            # Record usage
            self.context.llm_budget.record_llm_usage(tokens_used)
            
            # Cache the response
            self.llm_cache[cache_key] = response
            
            logger.info(f"Generated LLM response using {tokens_used} tokens")
            return response
            
        except Exception as e:
            logger.error(f"LLM response generation failed: {e}")
            raise
    
    def _build_system_prompt(self, current_state: DialogState) -> str:
        """Build system prompt based on current state."""
        base_prompt = """You are a professional AI sales assistant conducting a phone conversation. 
        Be conversational, helpful, and focused on understanding the prospect's needs.
        Keep responses concise and natural for phone conversation.
        """
        
        state_prompts = {
            DialogState.GREETING: "You are greeting the prospect and establishing rapport. Be warm and professional.",
            DialogState.QUALIFICATION: "You are qualifying the prospect by understanding their role, company, and decision-making authority.",
            DialogState.NEEDS_ANALYSIS: "You are identifying the prospect's pain points and business needs. Ask probing questions.",
            DialogState.OBJECTION_HANDLING: "You are addressing concerns or objections. Be empathetic and provide value-focused responses.",
            DialogState.CLOSING: "You are attempting to close the conversation with a next step. Be confident but not pushy."
        }
        
        state_specific = state_prompts.get(current_state, "Continue the professional conversation.")
        return f"{base_prompt}\n\nCurrent context: {state_specific}"
    
    def _build_conversation_context(self) -> ConversationContext:
        """Build conversation context for LLM."""
        return ConversationContext(
            call_sid=self.context.call_sid,
            turns=self.context.conversation_history,
            extracted_information=self.context.extracted_information
        )
    
    async def _analyze_response_for_state_transition(self, response: str, user_input: str) -> Optional[DialogState]:
        """Analyze response to determine if state transition is needed."""
        current_state = DialogState(self.current_state.id)
        response_lower = response.lower()
        user_input_lower = user_input.lower()
        
        # Simple rule-based state transition logic
        if current_state == DialogState.GREETING:
            if any(word in response_lower for word in ['qualify', 'role', 'position', 'company']):
                return DialogState.QUALIFICATION
        
        elif current_state == DialogState.QUALIFICATION:
            if any(word in response_lower for word in ['needs', 'challenges', 'pain', 'problems']):
                return DialogState.NEEDS_ANALYSIS
        
        elif current_state == DialogState.NEEDS_ANALYSIS:
            if any(word in user_input_lower for word in ['but', 'however', 'concern', 'worried']):
                return DialogState.OBJECTION_HANDLING
            elif any(word in response_lower for word in ['demo', 'trial', 'next step', 'schedule']):
                return DialogState.CLOSING
        
        elif current_state == DialogState.OBJECTION_HANDLING:
            if any(word in response_lower for word in ['demo', 'trial', 'next step']):
                return DialogState.CLOSING
            elif any(word in user_input_lower for word in ['not interested', 'no thanks', 'goodbye']):
                return DialogState.ABANDONED
        
        elif current_state == DialogState.CLOSING:
            if any(word in user_input_lower for word in ['yes', 'sure', 'okay', 'sounds good']):
                return DialogState.COMPLETED
            elif any(word in user_input_lower for word in ['but', 'however', 'concern']):
                return DialogState.OBJECTION_HANDLING
        
        return None
    
    async def _transition_to_state(self, next_state: DialogState):
        """Transition to the next state."""
        try:
            if next_state == DialogState.QUALIFICATION:
                await self.start_conversation()
            elif next_state == DialogState.NEEDS_ANALYSIS:
                await self.qualify_prospect()
            elif next_state == DialogState.OBJECTION_HANDLING:
                await self.analyze_needs()
            elif next_state == DialogState.CLOSING:
                await self.handle_objection()
            elif next_state == DialogState.COMPLETED:
                await self.complete_call()
            elif next_state == DialogState.ABANDONED:
                await self.abandon_call()
            elif next_state == DialogState.TRANSFERRED:
                await self.transfer_human()
            
            self.context.current_state = next_state
            self.context.reset_state_timer()
            
            logger.info(f"Transitioned to state: {next_state.value}")
            
        except Exception as e:
            logger.error(f"State transition failed: {e}")
    
    async def _get_fallback_response(self, current_state: DialogState, user_input: str) -> Tuple[str, bool]:
        """Get fallback response when templates and LLM are not available."""
        fallback_responses = {
            DialogState.GREETING: ("Thank you for taking my call. How are you doing today?", False),
            DialogState.QUALIFICATION: ("That's interesting. Can you tell me more about your role at the company?", False),
            DialogState.NEEDS_ANALYSIS: ("I'd love to understand your current challenges better. What are your biggest pain points?", False),
            DialogState.OBJECTION_HANDLING: ("I understand your concern. Let me see how we can address that.", False),
            DialogState.CLOSING: ("Based on our conversation, I think we could really help. Would you be interested in learning more?", False),
            DialogState.COMPLETED: ("Thank you so much for your time today. We'll be in touch soon!", True),
            DialogState.ABANDONED: ("I understand. Thank you for your time, and have a great day!", True),
            DialogState.TRANSFERRED: ("Let me transfer you to one of our specialists who can help you better.", True)
        }
        
        return fallback_responses.get(current_state, ("I see. Can you tell me more about that?", False))
    
    # State machine event handlers
    async def on_enter_state(self, target: State, event: str):
        """Handle state entry."""
        logger.info(f"Entering state: {target.id} via event: {event}")
        self.context.current_state = DialogState(target.id)
        self.context.reset_state_timer()
    
    async def on_exit_state(self, source: State, event: str):
        """Handle state exit."""
        logger.info(f"Exiting state: {source.id} via event: {event}")
    
    async def before_transition(self, event: str, source: State, target: State):
        """Handle before transition."""
        logger.debug(f"Before transition: {source.id} -> {target.id} via {event}")
    
    async def after_transition(self, event: str, source: State, target: State):
        """Handle after transition."""
        logger.debug(f"After transition: {source.id} -> {target.id} via {event}")


class DialogManager:
    """
    Main dialog management service that orchestrates conversation flow.
    
    Integrates FSM-based dialog management with template-first responses,
    selective LLM usage, and strict budget controls.
    """
    
    def __init__(self):
        self.template_library = DialogTemplateLibrary()
        self.active_conversations: Dict[str, ConversationStateMachine] = {}
        self.conversation_contexts: Dict[str, DialogContext] = {}
        
        logger.info("Dialog Manager initialized with template-first approach")
    
    async def start_conversation(self, call_sid: str, prospect_data: Dict[str, Any]) -> str:
        """
        Start a new conversation with FSM-based dialog management.
        
        Args:
            call_sid: Twilio Call SID
            prospect_data: Prospect information from research
            
        Returns:
            Initial greeting response
        """
        try:
            # Determine if prospect is VIP based on lead score
            lead_score = prospect_data.get('lead_score', 0)
            is_vip = lead_score >= 80
            
            # Create dialog context
            context = DialogContext(
                call_sid=call_sid,
                prospect_data=prospect_data,
                conversation_history=[],
                extracted_information={},
                current_state=DialogState.GREETING,
                state_entry_time=datetime.utcnow(),
                llm_budget=LLMBudgetTracker(is_vip=is_vip)
            )
            
            # Create state machine
            state_machine = ConversationStateMachine(context, self.template_library)
            
            # Store active conversation
            self.active_conversations[call_sid] = state_machine
            self.conversation_contexts[call_sid] = context
            
            # Generate initial greeting
            greeting_template = self.template_library.find_best_template(
                DialogState.GREETING, context
            )
            
            if greeting_template:
                response = greeting_template.response
            else:
                response = "Hello! Thank you for taking my call. I'm an AI assistant calling on behalf of our sales team. How are you doing today?"
            
            # Update conversation history
            context.conversation_history.append({
                'role': 'assistant',
                'content': response,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Started conversation for call {call_sid} (VIP: {is_vip})")
            return response
            
        except Exception as e:
            logger.error(f"Failed to start conversation for call {call_sid}: {e}")
            return "Hello! Thank you for taking my call. How can I help you today?"
    
    async def process_turn(self, call_sid: str, user_input: str) -> Tuple[str, bool]:
        """
        Process a conversation turn using FSM-based dialog management.
        
        Args:
            call_sid: Twilio Call SID
            user_input: User's speech input
            
        Returns:
            Tuple of (AI response, should_end_call)
        """
        try:
            state_machine = self.active_conversations.get(call_sid)
            
            if not state_machine:
                logger.warning(f"No active conversation found for call {call_sid}")
                return "I'm sorry, I seem to have lost our conversation context. Could you please repeat that?", False
            
            # Process user input through state machine
            response, should_end = await state_machine.process_user_input(user_input)
            
            logger.info(f"Processed turn for call {call_sid}, current state: {state_machine.current_state.id}")
            return response, should_end
            
        except Exception as e:
            logger.error(f"Failed to process turn for call {call_sid}: {e}")
            return "I'm sorry, I'm having some technical difficulties. Let me transfer you to a human representative.", True
    
    async def end_conversation(self, call_sid: str, reason: str = "completed") -> Dict[str, Any]:
        """
        End a conversation and cleanup resources.
        
        Args:
            call_sid: Twilio Call SID
            reason: Reason for ending conversation
            
        Returns:
            Conversation summary and metrics
        """
        try:
            state_machine = self.active_conversations.get(call_sid)
            context = self.conversation_contexts.get(call_sid)
            
            if not state_machine or not context:
                logger.warning(f"No conversation found for call {call_sid}")
                return {}
            
            # Generate conversation summary
            summary = {
                'call_sid': call_sid,
                'final_state': state_machine.current_state.id,
                'reason': reason,
                'duration_minutes': (datetime.utcnow() - context.state_entry_time).total_seconds() / 60,
                'total_turns': len(context.conversation_history),
                'llm_calls_used': context.llm_budget.current_llm_calls,
                'tokens_used': context.llm_budget.current_tokens_used,
                'objections_handled': len(context.objections_handled),
                'closing_attempts': context.closing_attempts,
                'extracted_information': context.extracted_information
            }
            
            # Cleanup
            self.active_conversations.pop(call_sid, None)
            self.conversation_contexts.pop(call_sid, None)
            
            logger.info(f"Ended conversation for call {call_sid}: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to end conversation for call {call_sid}: {e}")
            return {}
    
    async def get_conversation_status(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Get current conversation status."""
        try:
            state_machine = self.active_conversations.get(call_sid)
            context = self.conversation_contexts.get(call_sid)
            
            if not state_machine or not context:
                return None
            
            return {
                'call_sid': call_sid,
                'current_state': state_machine.current_state.id,
                'state_duration_seconds': (datetime.utcnow() - context.state_entry_time).total_seconds(),
                'total_turns': len(context.conversation_history),
                'llm_budget_used': {
                    'calls_used': context.llm_budget.current_llm_calls,
                    'calls_remaining': (context.llm_budget.max_llm_calls_vip if context.llm_budget.is_vip 
                                      else context.llm_budget.max_llm_calls_non_vip) - context.llm_budget.current_llm_calls,
                    'tokens_used': context.llm_budget.current_tokens_used
                },
                'is_timeout_risk': context.is_timeout()
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation status for call {call_sid}: {e}")
            return None


# Global instance
dialog_manager = DialogManager()