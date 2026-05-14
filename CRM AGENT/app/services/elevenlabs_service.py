"""
ElevenLabs Speech Services integration for high-quality STT and TTS.
"""
import asyncio
import io
import time
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
import tempfile
import os

import structlog
import httpx
from elevenlabs import ElevenLabs, VoiceSettings
import aiohttp

from app.core.config import get_settings


logger = structlog.get_logger()


class ElevenLabsService:
    """Service for ElevenLabs speech-to-text and text-to-speech operations."""
    
    def __init__(self):
        """Initialize ElevenLabs service with configuration."""
        self.settings = get_settings()
        self.client = ElevenLabs(api_key=self.settings.ELEVENLABS_API_KEY)
        
        # Voice settings optimized for phone calls
        self.voice_settings = VoiceSettings(
            stability=0.75,  # Higher stability for consistent phone quality
            similarity_boost=0.85,  # Good similarity for natural sound
            style=0.2,  # Lower style for professional tone
            use_speaker_boost=True  # Enhance clarity for phone calls
        )
        
        # Default voice ID (can be overridden)
        self.default_voice_id = self.settings.ELEVENLABS_VOICE_ID or "21m00Tcm4TlvDq8ikWAM"  # Rachel voice
        
        # API usage tracking
        self.api_usage = {
            'characters_used': 0,
            'requests_made': 0,
            'last_reset': time.time(),
            'rate_limit_remaining': 1000,  # Default limit
            'rate_limit_reset': time.time() + 3600  # Reset in 1 hour
        }
        
        # Audio quality settings for phone calls
        self.audio_settings = {
            'model_id': 'eleven_turbo_v2',  # Fastest model for real-time
            'output_format': 'mp3_44100_128',  # Good quality for phone
            'optimize_streaming_latency': 4,  # Optimize for low latency
            'chunk_length_schedule': [120, 160, 250, 290]  # Streaming chunks
        }
        
    async def transcribe_audio(
        self,
        audio_url: str,
        language: str = "en",
        fallback_enabled: bool = True
    ) -> Optional[str]:
        """
        Transcribe audio from URL to text using ElevenLabs STT.
        
        Args:
            audio_url: URL of audio file to transcribe
            language: Language code for transcription
            fallback_enabled: Whether to enable fallback logic
            
        Returns:
            Transcribed text or None if failed
        """
        try:
            # Download audio file
            audio_data = await self._download_audio(audio_url)
            if not audio_data:
                logger.warning("Failed to download audio for transcription", audio_url=audio_url)
                return None
            
            # Check audio quality before transcription
            quality_score = await self._assess_audio_quality(audio_data)
            if quality_score < 0.3 and fallback_enabled:
                logger.warning(
                    "Low audio quality detected, may affect transcription accuracy",
                    quality_score=quality_score,
                    audio_url=audio_url
                )
            
            # Perform transcription
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_file.flush()
                
                try:
                    # Use ElevenLabs STT API
                    transcription = await self._perform_transcription(temp_file.name, language)
                    
                    if transcription and len(transcription.strip()) > 0:
                        # Update usage tracking
                        self._update_usage_stats('stt', len(audio_data))
                        
                        logger.info(
                            "Successfully transcribed audio",
                            audio_url=audio_url,
                            transcription_length=len(transcription),
                            quality_score=quality_score
                        )
                        
                        return transcription.strip()
                    else:
                        logger.warning("Empty transcription result", audio_url=audio_url)
                        return None
                        
                finally:
                    # Clean up temp file
                    try:
                        os.unlink(temp_file.name)
                    except OSError:
                        pass
                        
        except Exception as e:
            logger.error(
                "Error during audio transcription",
                audio_url=audio_url,
                error=str(e),
                error_type=type(e).__name__
            )
            
            if fallback_enabled:
                return await self._transcription_fallback(audio_url)
            
            return None
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        optimize_for_phone: bool = True,
        streaming: bool = False
    ) -> Optional[bytes]:
        """
        Convert text to speech using ElevenLabs TTS.
        
        Args:
            text: Text to convert to speech
            voice_id: Voice ID to use (defaults to configured voice)
            optimize_for_phone: Whether to optimize audio for phone calls
            streaming: Whether to use streaming generation
            
        Returns:
            Audio data as bytes or None if failed
        """
        try:
            # Validate input text
            if not text or len(text.strip()) == 0:
                logger.warning("Empty text provided for speech synthesis")
                return None
            
            # Check text length limits
            if len(text) > 5000:  # ElevenLabs limit
                logger.warning(
                    "Text too long for synthesis, truncating",
                    original_length=len(text)
                )
                text = text[:4900] + "..."
            
            # Check rate limits
            if not await self._check_rate_limits('tts', len(text)):
                logger.warning("Rate limit exceeded for TTS request")
                return await self._tts_fallback(text)
            
            # Use provided voice or default
            target_voice_id = voice_id or self.default_voice_id
            
            # Optimize settings for phone calls
            voice_settings = self.voice_settings
            if optimize_for_phone:
                voice_settings = VoiceSettings(
                    stability=0.8,  # Higher stability for phone clarity
                    similarity_boost=0.75,  # Balanced for phone quality
                    style=0.1,  # Minimal style for professional tone
                    use_speaker_boost=True
                )
            
            # Generate speech
            if streaming:
                audio_data = await self._generate_streaming_speech(
                    text, target_voice_id, voice_settings
                )
            else:
                audio_data = await self._generate_speech(
                    text, target_voice_id, voice_settings
                )
            
            if audio_data:
                # Update usage tracking
                self._update_usage_stats('tts', len(text))
                
                logger.info(
                    "Successfully synthesized speech",
                    text_length=len(text),
                    voice_id=target_voice_id,
                    audio_size=len(audio_data),
                    streaming=streaming
                )
                
                return audio_data
            else:
                logger.warning("Failed to generate speech audio", text_length=len(text))
                return await self._tts_fallback(text)
                
        except Exception as e:
            logger.error(
                "Error during speech synthesis",
                text_length=len(text) if text else 0,
                voice_id=voice_id,
                error=str(e),
                error_type=type(e).__name__
            )
            
            return await self._tts_fallback(text)
    
    async def get_available_voices(self) -> List[Dict[str, Any]]:
        """
        Get list of available voices from ElevenLabs.
        
        Returns:
            List of voice information dictionaries
        """
        try:
            voices_response = self.client.voices.get_all()
            
            voice_list = []
            for voice in voices_response.voices:
                voice_info = {
                    'voice_id': voice.voice_id,
                    'name': voice.name,
                    'category': getattr(voice, 'category', 'unknown'),
                    'description': getattr(voice, 'description', ''),
                    'preview_url': getattr(voice, 'preview_url', ''),
                    'available_for_tiers': getattr(voice, 'available_for_tiers', []),
                    'settings': {
                        'stability': voice.settings.stability if voice.settings else 0.75,
                        'similarity_boost': voice.settings.similarity_boost if voice.settings else 0.75,
                        'style': getattr(voice.settings, 'style', 0.0) if voice.settings else 0.0,
                        'use_speaker_boost': getattr(voice.settings, 'use_speaker_boost', True) if voice.settings else True
                    }
                }
                voice_list.append(voice_info)
            
            logger.info("Retrieved available voices", voice_count=len(voice_list))
            return voice_list
            
        except Exception as e:
            logger.error("Error retrieving available voices", error=str(e))
            return []
    
    async def check_api_usage(self) -> Dict[str, Any]:
        """
        Check current API usage and limits.
        
        Returns:
            Dictionary with usage information
        """
        try:
            # Get subscription info from ElevenLabs
            user_info = self.client.user.get()
            subscription = user_info.subscription
            
            usage_info = {
                'character_count': subscription.character_count,
                'character_limit': subscription.character_limit,
                'characters_remaining': subscription.character_limit - subscription.character_count,
                'next_character_count_reset_unix': getattr(subscription, 'next_character_count_reset_unix', None),
                'voice_limit': getattr(subscription, 'voice_limit', 0),
                'professional_voice_limit': getattr(subscription, 'professional_voice_limit', 0),
                'can_extend_character_limit': getattr(subscription, 'can_extend_character_limit', False),
                'allowed_to_extend_character_limit': getattr(subscription, 'allowed_to_extend_character_limit', False),
                'next_invoice_date': getattr(subscription, 'next_invoice_date', None),
                'status': getattr(subscription, 'status', 'unknown'),
                'tier': subscription.tier,
                'local_usage': self.api_usage
            }
            
            logger.info("Retrieved API usage information")
            return usage_info
            
        except Exception as e:
            logger.error("Error checking API usage", error=str(e))
            return {'error': str(e), 'local_usage': self.api_usage}
    
    async def optimize_voice_for_phone(self, voice_id: str) -> VoiceSettings:
        """
        Get optimized voice settings for phone call quality.
        
        Args:
            voice_id: Voice ID to optimize
            
        Returns:
            Optimized VoiceSettings object
        """
        try:
            # Get voice details
            voice = self.client.voices.get(voice_id)
            
            # Create phone-optimized settings
            base_stability = voice.settings.stability if voice.settings else 0.75
            base_similarity = voice.settings.similarity_boost if voice.settings else 0.75
            base_style = getattr(voice.settings, 'style', 0.0) if voice.settings else 0.0
            
            optimized_settings = VoiceSettings(
                stability=min(0.85, base_stability + 0.1),
                similarity_boost=max(0.7, base_similarity - 0.05),
                style=min(0.2, base_style),
                use_speaker_boost=True  # Always enable for phone calls
            )
            
            logger.info(
                "Optimized voice settings for phone calls",
                voice_id=voice_id,
                stability=optimized_settings.stability,
                similarity_boost=optimized_settings.similarity_boost,
                style=optimized_settings.style
            )
            
            return optimized_settings
            
        except Exception as e:
            logger.error("Error optimizing voice settings", voice_id=voice_id, error=str(e))
            return self.voice_settings  # Return default settings
    
    async def _download_audio(self, audio_url: str) -> Optional[bytes]:
        """Download audio file from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(audio_url, timeout=30) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.warning(
                            "Failed to download audio",
                            audio_url=audio_url,
                            status_code=response.status
                        )
                        return None
        except Exception as e:
            logger.error("Error downloading audio", audio_url=audio_url, error=str(e))
            return None
    
    async def _assess_audio_quality(self, audio_data: bytes) -> float:
        """
        Assess audio quality for transcription accuracy prediction.
        
        Args:
            audio_data: Raw audio data
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            # Simple heuristics for audio quality assessment
            audio_size = len(audio_data)
            
            # Very small files are likely poor quality
            if audio_size < 1000:  # Less than 1KB
                return 0.1
            
            # Check for reasonable file size (rough estimate)
            if audio_size < 5000:  # Less than 5KB for short audio
                return 0.3
            elif audio_size > 100000:  # More than 100KB might be good quality
                return 0.8
            else:
                # Linear interpolation between thresholds
                return 0.3 + (audio_size - 5000) / (100000 - 5000) * 0.5
                
        except Exception as e:
            logger.error("Error assessing audio quality", error=str(e))
            return 0.5  # Default moderate quality score
    
    async def _perform_transcription(self, audio_file_path: str, language: str) -> Optional[str]:
        """Perform actual transcription using external STT service."""
        try:
            # Note: ElevenLabs doesn't provide STT service
            # This is a placeholder for integration with other STT services like OpenAI Whisper
            logger.info("Transcription requested but ElevenLabs doesn't provide STT service")
            
            # In a real implementation, you would integrate with:
            # - OpenAI Whisper API
            # - Google Speech-to-Text
            # - Azure Speech Services
            # - AWS Transcribe
            
            # For now, return None to indicate transcription is not available
            return None
                            
        except Exception as e:
            logger.error("Error performing transcription", error=str(e))
            return None
    
    async def _transcription_fallback(self, audio_url: str) -> Optional[str]:
        """Fallback transcription method when primary fails."""
        try:
            # For now, return None to indicate transcription failed
            # In a production system, you might integrate with other STT services
            logger.info("Transcription fallback triggered", audio_url=audio_url)
            return None
            
        except Exception as e:
            logger.error("Error in transcription fallback", error=str(e))
            return None
    
    async def _generate_speech(
        self,
        text: str,
        voice_id: str,
        voice_settings: VoiceSettings
    ) -> Optional[bytes]:
        """Generate speech using standard ElevenLabs TTS."""
        try:
            # Use the new API structure
            audio = self.client.text_to_speech.convert(
                text=text,
                voice_id=voice_id,
                model_id=self.audio_settings['model_id'],
                output_format=self.audio_settings['output_format'],
                voice_settings=voice_settings
            )
            
            return audio
            
        except Exception as e:
            logger.error("Error generating speech", error=str(e))
            return None
    
    async def _generate_streaming_speech(
        self,
        text: str,
        voice_id: str,
        voice_settings: VoiceSettings
    ) -> Optional[bytes]:
        """Generate speech using streaming for lower latency."""
        try:
            # For streaming, we'll collect all chunks into a single audio file
            audio_chunks = []
            
            # Use ElevenLabs streaming API
            audio_stream = self.client.text_to_speech.convert_as_stream(
                text=text,
                voice_id=voice_id,
                model_id=self.audio_settings['model_id'],
                output_format=self.audio_settings['output_format'],
                voice_settings=voice_settings
            )
            
            for chunk in audio_stream:
                if chunk:
                    audio_chunks.append(chunk)
            
            if audio_chunks:
                return b''.join(audio_chunks)
            else:
                return None
                
        except Exception as e:
            logger.error("Error generating streaming speech", error=str(e))
            return None
    
    async def _tts_fallback(self, text: str) -> Optional[bytes]:
        """Fallback TTS method when primary fails."""
        try:
            # For now, return None to indicate TTS failed
            # In a production system, you might use a simpler TTS service
            logger.info("TTS fallback triggered", text_length=len(text))
            return None
            
        except Exception as e:
            logger.error("Error in TTS fallback", error=str(e))
            return None
    
    async def _check_rate_limits(self, operation: str, content_size: int) -> bool:
        """Check if operation is within rate limits."""
        try:
            current_time = time.time()
            
            # Reset counters if needed
            if current_time > self.api_usage['rate_limit_reset']:
                self.api_usage['rate_limit_remaining'] = 1000  # Reset limit
                self.api_usage['rate_limit_reset'] = current_time + 3600  # Next hour
                self.api_usage['requests_made'] = 0
            
            # Check request rate limit
            if self.api_usage['requests_made'] >= 100:  # Max requests per hour
                return False
            
            # Check character limit for TTS
            if operation == 'tts' and content_size > self.api_usage['rate_limit_remaining']:
                return False
            
            return True
            
        except Exception as e:
            logger.error("Error checking rate limits", error=str(e))
            return True  # Allow operation if check fails
    
    def _update_usage_stats(self, operation: str, content_size: int):
        """Update internal usage statistics."""
        try:
            self.api_usage['requests_made'] += 1
            
            if operation == 'tts':
                self.api_usage['characters_used'] += content_size
                self.api_usage['rate_limit_remaining'] -= content_size
            
            logger.debug(
                "Updated usage stats",
                operation=operation,
                content_size=content_size,
                total_requests=self.api_usage['requests_made'],
                characters_used=self.api_usage['characters_used']
            )
            
        except Exception as e:
            logger.error("Error updating usage stats", error=str(e))


# Global instance
elevenlabs_service = ElevenLabsService()