"""
Pydantic schemas for speech processing operations.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator


class TranscriptionRequest(BaseModel):
    """Request schema for audio transcription."""
    
    audio_url: str = Field(..., description="URL of audio file to transcribe")
    language: str = Field(default="en", description="Language code for transcription")
    fallback_enabled: bool = Field(default=True, description="Enable fallback transcription methods")
    
    @validator("audio_url")
    def validate_audio_url(cls, v):
        """Validate audio URL format."""
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid audio URL format")
        return v
    
    @validator("language")
    def validate_language(cls, v):
        """Validate language code."""
        valid_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'pl', 'tr', 'ru', 'nl', 'cs', 'ar', 'zh', 'ja', 'hu', 'ko']
        if v not in valid_languages:
            raise ValueError(f"Unsupported language code: {v}")
        return v


class TranscriptionResponse(BaseModel):
    """Response schema for audio transcription."""
    
    success: bool = Field(..., description="Whether transcription was successful")
    text: Optional[str] = Field(None, description="Transcribed text")
    confidence: Optional[float] = Field(None, description="Transcription confidence score")
    language_detected: Optional[str] = Field(None, description="Detected language code")
    audio_duration: Optional[float] = Field(None, description="Audio duration in seconds")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    quality_score: Optional[float] = Field(None, description="Audio quality assessment score")
    error_message: Optional[str] = Field(None, description="Error message if transcription failed")
    fallback_used: bool = Field(default=False, description="Whether fallback method was used")
    
    @validator("confidence")
    def validate_confidence(cls, v):
        """Validate confidence score range."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Confidence score must be between 0.0 and 1.0")
        return v
    
    @validator("quality_score")
    def validate_quality_score(cls, v):
        """Validate quality score range."""
        if v is not None and (v < 0.0 or v > 1.0):
            raise ValueError("Quality score must be between 0.0 and 1.0")
        return v


class SynthesisRequest(BaseModel):
    """Request schema for text-to-speech synthesis."""
    
    text: str = Field(..., min_length=1, max_length=5000, description="Text to convert to speech")
    voice_id: Optional[str] = Field(None, description="Voice ID to use for synthesis")
    optimize_for_phone: bool = Field(default=True, description="Optimize audio for phone calls")
    streaming: bool = Field(default=False, description="Use streaming generation for lower latency")
    stability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice stability setting")
    similarity_boost: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice similarity boost setting")
    style: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice style setting")
    use_speaker_boost: Optional[bool] = Field(None, description="Enable speaker boost for clarity")
    
    @validator("text")
    def validate_text(cls, v):
        """Validate text content."""
        if not v.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        return v.strip()


class SynthesisResponse(BaseModel):
    """Response schema for text-to-speech synthesis."""
    
    success: bool = Field(..., description="Whether synthesis was successful")
    audio_data: Optional[bytes] = Field(None, description="Generated audio data")
    audio_url: Optional[str] = Field(None, description="URL to generated audio file")
    audio_format: str = Field(default="mp3", description="Audio format")
    audio_size: Optional[int] = Field(None, description="Audio file size in bytes")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    voice_id: Optional[str] = Field(None, description="Voice ID used for synthesis")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    character_count: Optional[int] = Field(None, description="Number of characters processed")
    error_message: Optional[str] = Field(None, description="Error message if synthesis failed")
    fallback_used: bool = Field(default=False, description="Whether fallback method was used")
    
    class Config:
        arbitrary_types_allowed = True  # Allow bytes type


class VoiceInfo(BaseModel):
    """Schema for voice information."""
    
    voice_id: str = Field(..., description="Unique voice identifier")
    name: str = Field(..., description="Voice name")
    category: Optional[str] = Field(None, description="Voice category")
    description: Optional[str] = Field(None, description="Voice description")
    preview_url: Optional[str] = Field(None, description="URL to voice preview")
    available_for_tiers: List[str] = Field(default_factory=list, description="Available subscription tiers")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Default voice settings")
    optimized_for_phone: bool = Field(default=False, description="Whether voice is optimized for phone calls")


class VoiceSettings(BaseModel):
    """Schema for voice configuration settings."""
    
    stability: float = Field(default=0.75, ge=0.0, le=1.0, description="Voice stability (0.0-1.0)")
    similarity_boost: float = Field(default=0.75, ge=0.0, le=1.0, description="Voice similarity boost (0.0-1.0)")
    style: float = Field(default=0.0, ge=0.0, le=1.0, description="Voice style (0.0-1.0)")
    use_speaker_boost: bool = Field(default=True, description="Enable speaker boost for clarity")


class ApiUsageInfo(BaseModel):
    """Schema for API usage information."""
    
    character_count: int = Field(..., description="Characters used this period")
    character_limit: int = Field(..., description="Character limit for current plan")
    characters_remaining: int = Field(..., description="Characters remaining this period")
    next_character_count_reset_unix: Optional[int] = Field(None, description="Next reset timestamp")
    voice_limit: int = Field(..., description="Maximum number of voices allowed")
    professional_voice_limit: int = Field(..., description="Maximum professional voices allowed")
    can_extend_character_limit: bool = Field(..., description="Whether character limit can be extended")
    allowed_to_extend_character_limit: bool = Field(..., description="Whether user is allowed to extend limit")
    next_invoice_date: Optional[str] = Field(None, description="Next billing date")
    status: str = Field(..., description="Subscription status")
    tier: str = Field(..., description="Subscription tier")
    local_usage: Dict[str, Any] = Field(default_factory=dict, description="Local usage tracking")


class AudioQualityAssessment(BaseModel):
    """Schema for audio quality assessment results."""
    
    quality_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score (0.0-1.0)")
    file_size: int = Field(..., description="Audio file size in bytes")
    estimated_duration: Optional[float] = Field(None, description="Estimated audio duration")
    quality_factors: Dict[str, Any] = Field(default_factory=dict, description="Detailed quality factors")
    recommendations: List[str] = Field(default_factory=list, description="Quality improvement recommendations")
    suitable_for_transcription: bool = Field(..., description="Whether audio is suitable for transcription")


class SpeechProcessingError(BaseModel):
    """Schema for speech processing error information."""
    
    error_type: str = Field(..., description="Type of error encountered")
    error_message: str = Field(..., description="Detailed error message")
    error_code: Optional[str] = Field(None, description="Error code if available")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    operation: str = Field(..., description="Operation that failed (transcription/synthesis)")
    input_data: Optional[Dict[str, Any]] = Field(None, description="Input data that caused the error")
    recovery_suggestions: List[str] = Field(default_factory=list, description="Suggested recovery actions")
    fallback_available: bool = Field(default=False, description="Whether fallback method is available")


class SpeechServiceHealth(BaseModel):
    """Schema for speech service health check."""
    
    service_name: str = Field(default="ElevenLabs", description="Speech service name")
    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    api_accessible: bool = Field(..., description="Whether API is accessible")
    response_time: Optional[float] = Field(None, description="API response time in seconds")
    rate_limit_status: Dict[str, Any] = Field(default_factory=dict, description="Rate limit information")
    last_successful_request: Optional[datetime] = Field(None, description="Last successful API request")
    error_rate: float = Field(default=0.0, description="Recent error rate percentage")
    available_voices: int = Field(default=0, description="Number of available voices")
    features_available: List[str] = Field(default_factory=list, description="Available service features")


class BatchTranscriptionRequest(BaseModel):
    """Schema for batch transcription requests."""
    
    audio_urls: List[str] = Field(..., min_items=1, max_items=10, description="List of audio URLs to transcribe")
    language: str = Field(default="en", description="Language code for transcription")
    fallback_enabled: bool = Field(default=True, description="Enable fallback transcription methods")
    parallel_processing: bool = Field(default=True, description="Process files in parallel")
    
    @validator("audio_urls")
    def validate_audio_urls(cls, v):
        """Validate all audio URLs."""
        for url in v:
            if not url or not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid audio URL format: {url}")
        return v


class BatchTranscriptionResponse(BaseModel):
    """Schema for batch transcription responses."""
    
    total_files: int = Field(..., description="Total number of files processed")
    successful_transcriptions: int = Field(..., description="Number of successful transcriptions")
    failed_transcriptions: int = Field(..., description="Number of failed transcriptions")
    results: List[TranscriptionResponse] = Field(..., description="Individual transcription results")
    processing_time: float = Field(..., description="Total processing time in seconds")
    batch_id: Optional[str] = Field(None, description="Batch processing identifier")