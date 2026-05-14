"""
Integration tests for ElevenLabs speech services.
"""
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
from elevenlabs import VoiceSettings

from app.services.elevenlabs_service import ElevenLabsService, elevenlabs_service
from app.schemas.speech import (
    TranscriptionRequest,
    TranscriptionResponse,
    SynthesisRequest,
    SynthesisResponse,
    VoiceInfo,
    ApiUsageInfo
)


class TestElevenLabsService:
    """Test cases for ElevenLabs speech service integration."""
    
    @pytest.fixture
    def service(self):
        """Create ElevenLabs service instance for testing."""
        return ElevenLabsService()
    
    @pytest.fixture
    def mock_audio_data(self):
        """Mock audio data for testing."""
        return b"fake_audio_data_for_testing" * 100  # Make it reasonably sized
    
    @pytest.fixture
    def sample_transcription_request(self):
        """Sample transcription request for testing."""
        return TranscriptionRequest(
            audio_url="https://example.com/audio.mp3",
            language="en",
            fallback_enabled=True
        )
    
    @pytest.fixture
    def sample_synthesis_request(self):
        """Sample synthesis request for testing."""
        return SynthesisRequest(
            text="Hello, this is a test message for speech synthesis.",
            voice_id="21m00Tcm4TlvDq8ikWAM",
            optimize_for_phone=True,
            streaming=False
        )
    
    def test_service_initialization(self, service):
        """Test service initializes correctly with configuration."""
        assert service.client is not None
        assert service.voice_settings is not None
        assert service.default_voice_id is not None
        assert service.audio_settings is not None
        assert isinstance(service.api_usage, dict)
        
        # Check voice settings are optimized for phone calls
        assert service.voice_settings.stability >= 0.7
        assert service.voice_settings.use_speaker_boost is True
    
    def test_voice_settings_phone_optimization(self, service):
        """Test voice settings are optimized for phone call quality."""
        settings = service.voice_settings
        
        # Phone-optimized settings should have higher stability
        assert settings.stability >= 0.7
        assert settings.similarity_boost >= 0.7
        assert settings.style <= 0.3  # Lower style for professional tone
        assert settings.use_speaker_boost is True
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_success(self, service, mock_audio_data):
        """Test successful audio transcription."""
        with patch.object(service, '_download_audio', return_value=mock_audio_data), \
             patch.object(service, '_assess_audio_quality', return_value=0.8), \
             patch.object(service, '_perform_transcription', return_value="Hello, this is a test transcription."):
            
            result = await service.transcribe_audio("https://example.com/audio.mp3")
            
            assert result is not None
            assert isinstance(result, str)
            assert len(result) > 0
            assert result == "Hello, this is a test transcription."
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_download_failure(self, service):
        """Test transcription when audio download fails."""
        with patch.object(service, '_download_audio', return_value=None):
            result = await service.transcribe_audio("https://example.com/invalid-audio.mp3")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_low_quality_with_fallback(self, service, mock_audio_data):
        """Test transcription with low quality audio and fallback enabled."""
        with patch.object(service, '_download_audio', return_value=mock_audio_data), \
             patch.object(service, '_assess_audio_quality', return_value=0.2), \
             patch.object(service, '_perform_transcription', return_value="Low quality transcription."):
            
            result = await service.transcribe_audio("https://example.com/low-quality.mp3", fallback_enabled=True)
            
            assert result is not None
            assert result == "Low quality transcription."
    
    @pytest.mark.asyncio
    async def test_transcribe_audio_fallback_disabled(self, service, mock_audio_data):
        """Test transcription with fallback disabled."""
        with patch.object(service, '_download_audio', return_value=mock_audio_data), \
             patch.object(service, '_assess_audio_quality', return_value=0.8), \
             patch.object(service, '_perform_transcription', side_effect=Exception("API Error")):
            
            result = await service.transcribe_audio("https://example.com/audio.mp3", fallback_enabled=False)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_success(self, service):
        """Test successful speech synthesis."""
        mock_audio = b"fake_generated_audio_data"
        
        with patch.object(service, '_check_rate_limits', return_value=True), \
             patch.object(service, '_generate_speech', return_value=mock_audio):
            
            result = await service.synthesize_speech("Hello, world!")
            
            assert result is not None
            assert isinstance(result, bytes)
            assert result == mock_audio
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_empty_text(self, service):
        """Test speech synthesis with empty text."""
        result = await service.synthesize_speech("")
        assert result is None
        
        result = await service.synthesize_speech("   ")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_long_text_truncation(self, service):
        """Test speech synthesis with text that exceeds length limits."""
        long_text = "A" * 6000  # Exceeds 5000 character limit
        mock_audio = b"truncated_audio_data"
        
        with patch.object(service, '_check_rate_limits', return_value=True), \
             patch.object(service, '_generate_speech', return_value=mock_audio) as mock_generate:
            
            result = await service.synthesize_speech(long_text)
            
            assert result is not None
            # Check that the text was truncated
            call_args = mock_generate.call_args[0]
            truncated_text = call_args[0]
            assert len(truncated_text) <= 5000
            assert truncated_text.endswith("...")
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_rate_limit_exceeded(self, service):
        """Test speech synthesis when rate limits are exceeded."""
        with patch.object(service, '_check_rate_limits', return_value=False), \
             patch.object(service, '_tts_fallback', return_value=None) as mock_fallback:
            
            result = await service.synthesize_speech("Hello, world!")
            
            assert result is None
            mock_fallback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_streaming(self, service):
        """Test streaming speech synthesis."""
        mock_audio = b"streaming_audio_data"
        
        with patch.object(service, '_check_rate_limits', return_value=True), \
             patch.object(service, '_generate_streaming_speech', return_value=mock_audio):
            
            result = await service.synthesize_speech("Hello, world!", streaming=True)
            
            assert result is not None
            assert result == mock_audio
    
    @pytest.mark.asyncio
    async def test_synthesize_speech_phone_optimization(self, service):
        """Test speech synthesis with phone optimization."""
        mock_audio = b"phone_optimized_audio"
        
        with patch.object(service, '_check_rate_limits', return_value=True), \
             patch.object(service, '_generate_speech', return_value=mock_audio) as mock_generate:
            
            result = await service.synthesize_speech(
                "Hello, world!",
                optimize_for_phone=True
            )
            
            assert result is not None
            
            # Check that phone-optimized settings were used
            call_args = mock_generate.call_args[0]
            voice_settings = call_args[2]
            assert voice_settings.stability >= 0.7
            assert voice_settings.use_speaker_boost is True
    
    @pytest.mark.asyncio
    async def test_get_available_voices(self, service):
        """Test retrieving available voices."""
        mock_voice = Mock()
        mock_voice.voice_id = "test_voice_id"
        mock_voice.name = "Test Voice"
        mock_voice.category = "premade"
        mock_voice.settings = Mock()
        mock_voice.settings.stability = 0.75
        mock_voice.settings.similarity_boost = 0.85
        
        mock_voices_response = Mock()
        mock_voices_response.voices = [mock_voice]
        
        with patch.object(service.client.voices, 'get_all', return_value=mock_voices_response):
            voices = await service.get_available_voices()
            
            assert len(voices) == 1
            assert voices[0]['voice_id'] == "test_voice_id"
            assert voices[0]['name'] == "Test Voice"
            assert voices[0]['category'] == "premade"
            assert 'settings' in voices[0]
    
    @pytest.mark.asyncio
    async def test_get_available_voices_error(self, service):
        """Test error handling when retrieving voices fails."""
        with patch.object(service.client.voices, 'get_all', side_effect=Exception("API Error")):
            voices = await service.get_available_voices()
            assert voices == []
    
    @pytest.mark.asyncio
    async def test_check_api_usage(self, service):
        """Test checking API usage and limits."""
        mock_subscription = Mock()
        mock_subscription.character_count = 1000
        mock_subscription.character_limit = 10000
        mock_subscription.next_character_count_reset_unix = 1234567890
        mock_subscription.voice_limit = 10
        mock_subscription.professional_voice_limit = 5
        mock_subscription.can_extend_character_limit = True
        mock_subscription.allowed_to_extend_character_limit = True
        mock_subscription.status = "active"
        mock_subscription.tier = "starter"
        
        mock_user = Mock()
        mock_user.subscription = mock_subscription
        
        with patch.object(service.client.user, 'get', return_value=mock_user):
            usage_info = await service.check_api_usage()
            
            assert usage_info['character_count'] == 1000
            assert usage_info['character_limit'] == 10000
            assert usage_info['characters_remaining'] == 9000
            assert usage_info['status'] == "active"
            assert usage_info['tier'] == "starter"
            assert 'local_usage' in usage_info
    
    @pytest.mark.asyncio
    async def test_check_api_usage_error(self, service):
        """Test error handling when checking API usage fails."""
        with patch.object(service.client.user, 'get', side_effect=Exception("API Error")):
            usage_info = await service.check_api_usage()
            
            assert 'error' in usage_info
            assert 'local_usage' in usage_info
    
    @pytest.mark.asyncio
    async def test_optimize_voice_for_phone(self, service):
        """Test voice optimization for phone calls."""
        mock_voice = Mock()
        mock_voice.settings = Mock()
        mock_voice.settings.stability = 0.7
        mock_voice.settings.similarity_boost = 0.8
        
        with patch.object(service.client.voices, 'get', return_value=mock_voice):
            optimized_settings = await service.optimize_voice_for_phone("test_voice_id")
            
            assert isinstance(optimized_settings, VoiceSettings)
            assert optimized_settings.stability >= 0.7
            assert optimized_settings.use_speaker_boost is True
            assert optimized_settings.style <= 0.2
    
    @pytest.mark.asyncio
    async def test_optimize_voice_for_phone_error(self, service):
        """Test error handling when optimizing voice settings fails."""
        with patch.object(service.client.voices, 'get', side_effect=Exception("API Error")):
            optimized_settings = await service.optimize_voice_for_phone("invalid_voice_id")
            
            # Should return default settings on error
            assert isinstance(optimized_settings, VoiceSettings)
            assert optimized_settings == service.voice_settings
    
    @pytest.mark.asyncio
    async def test_download_audio_success(self, service, mock_audio_data):
        """Test successful audio download."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=mock_audio_data)
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await service._download_audio("https://example.com/audio.mp3")
            
            assert result == mock_audio_data
    
    @pytest.mark.asyncio
    async def test_download_audio_failure(self, service):
        """Test audio download failure."""
        mock_response = AsyncMock()
        mock_response.status = 404
        
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session):
            result = await service._download_audio("https://example.com/nonexistent.mp3")
            
            assert result is None
    
    def test_assess_audio_quality(self, service):
        """Test audio quality assessment."""
        # Very small file - poor quality
        small_audio = b"small"
        quality = asyncio.run(service._assess_audio_quality(small_audio))
        assert quality == 0.1
        
        # Medium file - moderate quality
        medium_audio = b"A" * 50000
        quality = asyncio.run(service._assess_audio_quality(medium_audio))
        assert 0.3 <= quality <= 0.8
        
        # Large file - good quality
        large_audio = b"A" * 150000
        quality = asyncio.run(service._assess_audio_quality(large_audio))
        assert quality == 0.8
    
    def test_check_rate_limits(self, service):
        """Test rate limit checking."""
        # Reset usage stats
        service.api_usage = {
            'characters_used': 0,
            'requests_made': 0,
            'last_reset': 0,
            'rate_limit_remaining': 1000,
            'rate_limit_reset': 9999999999  # Far future
        }
        
        # Should allow operation within limits
        result = asyncio.run(service._check_rate_limits('tts', 100))
        assert result is True
        
        # Should deny operation exceeding character limit
        result = asyncio.run(service._check_rate_limits('tts', 2000))
        assert result is False
        
        # Should deny operation exceeding request limit
        service.api_usage['requests_made'] = 150
        result = asyncio.run(service._check_rate_limits('tts', 50))
        assert result is False
    
    def test_update_usage_stats(self, service):
        """Test usage statistics updating."""
        initial_requests = service.api_usage['requests_made']
        initial_characters = service.api_usage['characters_used']
        
        service._update_usage_stats('tts', 100)
        
        assert service.api_usage['requests_made'] == initial_requests + 1
        assert service.api_usage['characters_used'] == initial_characters + 100
        assert service.api_usage['rate_limit_remaining'] <= 1000
    
    def test_global_service_instance(self):
        """Test that global service instance is properly initialized."""
        assert elevenlabs_service is not None
        assert isinstance(elevenlabs_service, ElevenLabsService)
        assert elevenlabs_service.client is not None


class TestSpeechSchemas:
    """Test cases for speech processing schemas."""
    
    def test_transcription_request_validation(self):
        """Test transcription request validation."""
        # Valid request
        request = TranscriptionRequest(
            audio_url="https://example.com/audio.mp3",
            language="en"
        )
        assert request.audio_url == "https://example.com/audio.mp3"
        assert request.language == "en"
        assert request.fallback_enabled is True
        
        # Invalid URL
        with pytest.raises(ValueError, match="Invalid audio URL format"):
            TranscriptionRequest(audio_url="invalid-url", language="en")
        
        # Invalid language
        with pytest.raises(ValueError, match="Unsupported language code"):
            TranscriptionRequest(
                audio_url="https://example.com/audio.mp3",
                language="invalid"
            )
    
    def test_synthesis_request_validation(self):
        """Test synthesis request validation."""
        # Valid request
        request = SynthesisRequest(text="Hello, world!")
        assert request.text == "Hello, world!"
        assert request.optimize_for_phone is True
        assert request.streaming is False
        
        # Empty text
        with pytest.raises(ValueError, match="Text cannot be empty"):
            SynthesisRequest(text="")
        
        # Whitespace only text
        with pytest.raises(ValueError, match="Text cannot be empty"):
            SynthesisRequest(text="   ")
        
        # Text too long
        with pytest.raises(ValueError):
            SynthesisRequest(text="A" * 6000)
    
    def test_transcription_response_validation(self):
        """Test transcription response validation."""
        # Valid response
        response = TranscriptionResponse(
            success=True,
            text="Hello, world!",
            confidence=0.95,
            quality_score=0.8
        )
        assert response.success is True
        assert response.text == "Hello, world!"
        assert response.confidence == 0.95
        assert response.quality_score == 0.8
        
        # Invalid confidence score
        with pytest.raises(ValueError, match="Confidence score must be between 0.0 and 1.0"):
            TranscriptionResponse(success=True, confidence=1.5)
        
        # Invalid quality score
        with pytest.raises(ValueError, match="Quality score must be between 0.0 and 1.0"):
            TranscriptionResponse(success=True, quality_score=-0.1)
    
    def test_voice_settings_validation(self):
        """Test voice settings validation."""
        from app.schemas.speech import VoiceSettings
        
        # Valid settings
        settings = VoiceSettings(
            stability=0.8,
            similarity_boost=0.7,
            style=0.2,
            use_speaker_boost=True
        )
        assert settings.stability == 0.8
        assert settings.similarity_boost == 0.7
        assert settings.style == 0.2
        assert settings.use_speaker_boost is True
        
        # Invalid stability (out of range)
        with pytest.raises(ValueError):
            VoiceSettings(stability=1.5)
        
        # Invalid similarity_boost (out of range)
        with pytest.raises(ValueError):
            VoiceSettings(similarity_boost=-0.1)


@pytest.mark.integration
class TestElevenLabsIntegration:
    """Integration tests that require actual ElevenLabs API access."""
    
    @pytest.mark.skipif(
        not os.getenv("ELEVENLABS_API_KEY"),
        reason="ElevenLabs API key not provided"
    )
    @pytest.mark.asyncio
    async def test_real_api_voice_list(self):
        """Test retrieving voices from real API."""
        service = ElevenLabsService()
        voices = await service.get_available_voices()
        
        assert len(voices) > 0
        assert all('voice_id' in voice for voice in voices)
        assert all('name' in voice for voice in voices)
    
    @pytest.mark.skipif(
        not os.getenv("ELEVENLABS_API_KEY"),
        reason="ElevenLabs API key not provided"
    )
    @pytest.mark.asyncio
    async def test_real_api_usage_check(self):
        """Test checking usage from real API."""
        service = ElevenLabsService()
        usage_info = await service.check_api_usage()
        
        assert 'character_count' in usage_info
        assert 'character_limit' in usage_info
        assert 'status' in usage_info
        assert 'tier' in usage_info
    
    @pytest.mark.skipif(
        not os.getenv("ELEVENLABS_API_KEY"),
        reason="ElevenLabs API key not provided"
    )
    @pytest.mark.asyncio
    async def test_real_tts_generation(self):
        """Test actual TTS generation with real API."""
        service = ElevenLabsService()
        
        # Generate short audio to minimize API usage
        audio_data = await service.synthesize_speech(
            "Test",
            optimize_for_phone=True
        )
        
        assert audio_data is not None
        assert isinstance(audio_data, bytes)
        assert len(audio_data) > 0