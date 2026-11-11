"""Private, bounded answer dictation. Audio is never persisted by Athena."""
import os

from fastapi import HTTPException
from openai import AsyncOpenAI, OpenAIError

from ..operations import MODELS, ModelCapacity

MAX_AUDIO_BYTES = 2 * 1024 * 1024


async def transcribe_answer(audio: bytes, content_type: str) -> str:
    mime = content_type.split(';', 1)[0].strip().lower()
    formats = {'audio/webm': ('webm', lambda b: b.startswith(b'\x1aE\xdf\xa3')),
               'audio/mp4': ('mp4', lambda b: b[4:8] == b'ftyp'),
               'audio/ogg': ('ogg', lambda b: b.startswith(b'OggS')),
               'audio/wav': ('wav', lambda b: b.startswith(b'RIFF') and b[8:12] == b'WAVE')}
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, 'This recording is too large. Record a shorter answer or type it instead.')
    if not audio:
        raise HTTPException(422, 'No audio was recorded. Please try again or type your answer.')
    if mime not in formats or not formats[mime][1](audio):
        raise HTTPException(415, 'This audio format is not supported. Please type your answer instead.')
    if not os.environ.get('OPENAI_API_KEY', '').strip():
        raise HTTPException(503, 'Voice typing is unavailable. You can still type your answer.')
    try:
        with MODELS.slot():
            async with AsyncOpenAI(max_retries=0, timeout=30) as client:
                result = await client.audio.transcriptions.create(
                    model=os.environ.get('ATHENA_TRANSCRIPTION_MODEL', 'gpt-transcribe'),
                    file=(f'answer.{formats[mime][0]}', audio, mime),
                )
    except (OpenAIError, ModelCapacity):
        raise HTTPException(503, 'Voice typing could not finish. Try again or type your answer; your draft is safe.') from None
    text = result.text.strip()
    if not text:
        raise HTTPException(422, 'No speech was detected. Please try again or type your answer.')
    if len(text) > 4000:
        raise HTTPException(422, 'That answer is too long. Record a shorter answer or type a summary.')
    return text
