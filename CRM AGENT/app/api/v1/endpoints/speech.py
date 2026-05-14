"""
API endpoints for speech processing services.
"""
import tempfile
import os
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import Response
import structlog

from app.services.elevenlabs_service import elevenlabs_service
from app.schemas.speech import (
    TranscriptionRequest,
    TranscriptionResponse,
    SynthesisRequest,
    SynthesisResponse,
    VoiceInfo,
    ApiUsageInfo,
    SpeechServiceHealth,
    BatchTranscriptionRequest,
    BatchTranscriptionResponse
)

logger = structlog.get_logger()
router = APIRouter()


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: TranscriptionRequest):
    """
    Transcribe audio from URL to text using ElevenLabs STT.
    
    Args:
        request: Transcription request with audio URL and options
        
    Returns:
        TranscriptionResponse with transcribed text and metadata
    """
    try:
        logger.info(
            "Transcription request received",
            audio_url=request.audio_url,
            language=request.language,
            fallback_enabled=request.fallback_enabled
        )
        
        # Perform transcription
        transcribed_text = await elevenlabs_service.transcribe_audio(
            audio_url=request.audio_url,
            language=request.language,
            fallback_enabled=request.fallback_enabled
        )
        
        if transcribed_text:
            return TranscriptionResponse(
                success=True,
                text=transcribed_text,
                language_detected=request.language,
                fallback_used=False  # TODO: Track if fallback was used
            )
        else:
            return TranscriptionResponse(
                success=False,
                error_message="Transcription failed - audio may be unclear or service unavailable",
                fallback_used=request.fallback_enabled
            )
            
    except Exception as e:
        logger.error(
            "Error processing transcription request",
            audio_url=request.audio_url,
            error=str(e)
        )
        
        return TranscriptionResponse(
            success=False,
            error_message=f"Transcription error: {str(e)}",
            fallback_used=False
        )


@router.post("/transcribe-file", response_model=TranscriptionResponse)
async def transcribe_audio_file(
    audio_file: UploadFile = File(...),
    language: str = Form(default="en"),
    fallback_enabled: bool = Form(default=True)
):
    """
    Transcribe uploaded audio file to text.
    
    Args:
        audio_file: Uploaded audio file
        language: Language code for transcription
        fallback_enabled: Enable fallback transcription methods
        
    Returns:
        TranscriptionResponse with transcribed text and metadata
    """
    try:
        # Validate file type
        if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an audio file."
            )
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
            content = await audio_file.read()
            temp_file.write(content)
            temp_file.flush()
            
            try:
                # Create temporary URL for the file (in production, upload to cloud storage)
                temp_url = f"file://{temp_file.name}"
                
                # Perform transcription
                transcribed_text = await elevenlabs_service.transcribe_audio(
                    audio_url=temp_url,
                    language=language,
                    fallback_enabled=fallback_enabled
                )
                
                if transcribed_text:
                    return TranscriptionResponse(
                        success=True,
                        text=transcribed_text,
                        language_detected=language,
                        audio_duration=None,  # TODO: Calculate from file
                        fallback_used=False
                    )
                else:
                    return TranscriptionResponse(
                        success=False,
                        error_message="Transcription failed - audio may be unclear or service unavailable",
                        fallback_used=fallback_enabled
                    )
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file.name)
                except OSError:
                    pass
                    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error processing audio file transcription",
            filename=audio_file.filename,
            error=str(e)
        )
        
        return TranscriptionResponse(
            success=False,
            error_message=f"File transcription error: {str(e)}",
            fallback_used=False
        )


@router.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_speech(request: SynthesisRequest):
    """
    Convert text to speech using ElevenLabs TTS.
    
    Args:
        request: Synthesis request with text and voice options
        
    Returns:
        SynthesisResponse with audio data and metadata
    """
    try:
        logger.info(
            "Speech synthesis request received",
            text_length=len(request.text),
            voice_id=request.voice_id,
            optimize_for_phone=request.optimize_for_phone,
            streaming=request.streaming
        )
        
        # Perform speech synthesis
        audio_data = await elevenlabs_service.synthesize_speech(
            text=request.text,
            voice_id=request.voice_id,
            optimize_for_phone=request.optimize_for_phone,
            streaming=request.streaming
        )
        
        if audio_data:
            return SynthesisResponse(
                success=True,
                audio_data=audio_data,
                audio_format="mp3",
                audio_size=len(audio_data),
                voice_id=request.voice_id or elevenlabs_service.default_voice_id,
                character_count=len(request.text),
                fallback_used=False
            )
        else:
            return SynthesisResponse(
                success=False,
                error_message="Speech synthesis failed - service may be unavailable or rate limited",
                fallback_used=True
            )
            
    except Exception as e:
        logger.error(
            "Error processing speech synthesis request",
            text_length=len(request.text),
            error=str(e)
        )
        
        return SynthesisResponse(
            success=False,
            error_message=f"Synthesis error: {str(e)}",
            fallback_used=False
        )


@router.post("/synthesize-audio")
async def synthesize_speech_audio(request: SynthesisRequest):
    """
    Convert text to speech and return audio file directly.
    
    Args:
        request: Synthesis request with text and voice options
        
    Returns:
        Audio file as binary response
    """
    try:
        # Perform speech synthesis
        audio_data = await elevenlabs_service.synthesize_speech(
            text=request.text,
            voice_id=request.voice_id,
            optimize_for_phone=request.optimize_for_phone,
            streaming=request.streaming
        )
        
        if audio_data:
            return Response(
                content=audio_data,
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": "attachment; filename=speech.mp3",
                    "Content-Length": str(len(audio_data))
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Speech synthesis failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error generating speech audio",
            text_length=len(request.text),
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Speech synthesis error: {str(e)}"
        )


@router.get("/voices", response_model=List[VoiceInfo])
async def get_available_voices():
    """
    Get list of available voices from ElevenLabs.
    
    Returns:
        List of available voice information
    """
    try:
        voices = await elevenlabs_service.get_available_voices()
        
        return [
            VoiceInfo(
                voice_id=voice['voice_id'],
                name=voice['name'],
                category=voice.get('category'),
                description=voice.get('description'),
                preview_url=voice.get('preview_url'),
                available_for_tiers=voice.get('available_for_tiers', []),
                settings=voice.get('settings', {}),
                optimized_for_phone=voice.get('settings', {}).get('use_speaker_boost', False)
            )
            for voice in voices
        ]
        
    except Exception as e:
        logger.error("Error retrieving available voices", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve voices: {str(e)}"
        )


@router.get("/usage", response_model=ApiUsageInfo)
async def get_api_usage():
    """
    Get current API usage and limits for ElevenLabs.
    
    Returns:
        API usage information and limits
    """
    try:
        usage_info = await elevenlabs_service.check_api_usage()
        
        if 'error' in usage_info:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to retrieve usage info: {usage_info['error']}"
            )
        
        return ApiUsageInfo(**usage_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving API usage", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve usage info: {str(e)}"
        )


@router.get("/health", response_model=SpeechServiceHealth)
async def get_speech_service_health():
    """
    Get health status of speech processing services.
    
    Returns:
        Health status and service information
    """
    try:
        # Check service health
        usage_info = await elevenlabs_service.check_api_usage()
        voices = await elevenlabs_service.get_available_voices()
        
        # Determine health status
        if 'error' in usage_info:
            status = "unhealthy"
            api_accessible = False
            error_rate = 100.0
        else:
            characters_remaining = usage_info.get('characters_remaining', 0)
            if characters_remaining < 1000:
                status = "degraded"
            else:
                status = "healthy"
            api_accessible = True
            error_rate = 0.0
        
        return SpeechServiceHealth(
            service_name="ElevenLabs",
            status=status,
            api_accessible=api_accessible,
            rate_limit_status=usage_info.get('local_usage', {}),
            error_rate=error_rate,
            available_voices=len(voices),
            features_available=["transcription", "synthesis", "voice_optimization"]
        )
        
    except Exception as e:
        logger.error("Error checking speech service health", error=str(e))
        
        return SpeechServiceHealth(
            service_name="ElevenLabs",
            status="unhealthy",
            api_accessible=False,
            error_rate=100.0,
            available_voices=0,
            features_available=[]
        )


@router.post("/batch-transcribe", response_model=BatchTranscriptionResponse)
async def batch_transcribe_audio(
    request: BatchTranscriptionRequest,
    background_tasks: BackgroundTasks
):
    """
    Transcribe multiple audio files in batch.
    
    Args:
        request: Batch transcription request with multiple audio URLs
        background_tasks: FastAPI background tasks for async processing
        
    Returns:
        Batch transcription results
    """
    try:
        logger.info(
            "Batch transcription request received",
            file_count=len(request.audio_urls),
            language=request.language,
            parallel_processing=request.parallel_processing
        )
        
        results = []
        successful_count = 0
        failed_count = 0
        
        if request.parallel_processing:
            # Process files in parallel (limited concurrency)
            import asyncio
            
            async def transcribe_single(audio_url: str) -> TranscriptionResponse:
                try:
                    text = await elevenlabs_service.transcribe_audio(
                        audio_url=audio_url,
                        language=request.language,
                        fallback_enabled=request.fallback_enabled
                    )
                    
                    if text:
                        return TranscriptionResponse(
                            success=True,
                            text=text,
                            language_detected=request.language
                        )
                    else:
                        return TranscriptionResponse(
                            success=False,
                            error_message="Transcription failed"
                        )
                        
                except Exception as e:
                    return TranscriptionResponse(
                        success=False,
                        error_message=str(e)
                    )
            
            # Process with limited concurrency
            semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests
            
            async def transcribe_with_semaphore(url: str):
                async with semaphore:
                    return await transcribe_single(url)
            
            tasks = [transcribe_with_semaphore(url) for url in request.audio_urls]
            results = await asyncio.gather(*tasks)
            
        else:
            # Process files sequentially
            for audio_url in request.audio_urls:
                try:
                    text = await elevenlabs_service.transcribe_audio(
                        audio_url=audio_url,
                        language=request.language,
                        fallback_enabled=request.fallback_enabled
                    )
                    
                    if text:
                        results.append(TranscriptionResponse(
                            success=True,
                            text=text,
                            language_detected=request.language
                        ))
                        successful_count += 1
                    else:
                        results.append(TranscriptionResponse(
                            success=False,
                            error_message="Transcription failed"
                        ))
                        failed_count += 1
                        
                except Exception as e:
                    results.append(TranscriptionResponse(
                        success=False,
                        error_message=str(e)
                    ))
                    failed_count += 1
        
        # Count successes and failures
        if request.parallel_processing:
            successful_count = sum(1 for r in results if r.success)
            failed_count = len(results) - successful_count
        
        return BatchTranscriptionResponse(
            total_files=len(request.audio_urls),
            successful_transcriptions=successful_count,
            failed_transcriptions=failed_count,
            results=results,
            processing_time=0.0,  # TODO: Track actual processing time
            batch_id=None  # TODO: Generate batch ID for tracking
        )
        
    except Exception as e:
        logger.error(
            "Error processing batch transcription",
            file_count=len(request.audio_urls),
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Batch transcription error: {str(e)}"
        )


@router.post("/optimize-voice/{voice_id}")
async def optimize_voice_for_phone(voice_id: str):
    """
    Get phone-optimized settings for a specific voice.
    
    Args:
        voice_id: Voice ID to optimize
        
    Returns:
        Optimized voice settings
    """
    try:
        optimized_settings = await elevenlabs_service.optimize_voice_for_phone(voice_id)
        
        return {
            "voice_id": voice_id,
            "optimized_settings": {
                "stability": optimized_settings.stability,
                "similarity_boost": optimized_settings.similarity_boost,
                "style": optimized_settings.style,
                "use_speaker_boost": optimized_settings.use_speaker_boost
            },
            "optimization_type": "phone_call"
        }
        
    except Exception as e:
        logger.error(
            "Error optimizing voice settings",
            voice_id=voice_id,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail=f"Voice optimization error: {str(e)}"
        )