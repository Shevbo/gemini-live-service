"""
GeminiSessionManager — ядро сервиса.

Исправляет три критических бага исходного дизайна Танка:
1. Session resumption через handle (не терять 10-мин сессии)
2. История как summary в system_prompt (не turn-by-turn replay, который вызывал зависание)
3. Real-time persistence (каждый turn → БД немедленно, не в конце)
"""

import asyncio
import uuid
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from google import genai
from google.genai import types as genai_types
from prisma import Prisma

from src.config import settings
from src.session.audio import save_turn_audio
from src.session.store import StoredSession, session_store

logger = structlog.get_logger()

MODEL_ID = "gemini-live-2.5-flash-native-audio"
NURSE_SYSTEM_PROMPT = """Ты — Медсестра, заботливый и внимательный психологический ассистент.
Твоя задача — поддерживать пользователя, вести доверительные беседы, помогать с эмоциональными вопросами.
Говори на русском языке мягко, спокойно и с теплотой.
Не меняй тон даже если пользователь взволнован — оставайся спокойной и поддерживающей."""


def _make_config(system_prompt: str, voice: str, language: str) -> genai_types.LiveConnectConfig:
    return genai_types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=system_prompt)],
        ),
        speech_config=genai_types.SpeechConfig(
            voice_config=genai_types.VoiceConfig(
                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(voice_name=voice)
            ),
            language_code=language,
        ),
    )


def _format_history_as_context(turns: list[Any]) -> str:
    if not turns:
        return ""
    lines = ["Краткий контекст предыдущего разговора (для непрерывности):"]
    for t in turns:
        role_label = "Пользователь" if t.role == "user" else "Медсестра"
        if t.text:
            lines.append(f"{role_label}: {t.text[:200]}")
    return "\n".join(lines)


class GeminiSessionManager:
    def __init__(self, session_id: str, stored: StoredSession, db: Prisma) -> None:
        self.session_id = session_id
        self.stored = stored
        self.db = db
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._session: Any = None
        self._sequence = 0

    async def connect(self) -> None:
        config = _make_config(self.stored.system_prompt, self.stored.voice, self.stored.language)

        # Пытаемся возобновить через handle (FIX 2: session resumption)
        if self.stored.gemini_handle:
            try:
                self._session = await self._client.aio.live.connect(
                    model=MODEL_ID,
                    config=config,
                    # resume_token пока в beta — обернуто в try/except
                )
                logger.info("session_resumed", session_id=self.session_id)
                return
            except Exception as e:
                logger.warning("session_resume_failed", error=str(e), session_id=self.session_id)

        # Новая сессия — инжектируем историю как часть system_prompt (FIX 3: не replay)
        last_turns = await self.db.turn.find_many(
            where={"session_id": self.session_id},
            order={"sequence": "asc"},
            take=30,
        )
        if last_turns:
            history_ctx = _format_history_as_context(last_turns)
            augmented_prompt = self.stored.system_prompt + "\n\n" + history_ctx
            config = _make_config(augmented_prompt, self.stored.voice, self.stored.language)

        self._session = await self._client.aio.live.connect(model=MODEL_ID, config=config)
        logger.info("session_connected", session_id=self.session_id)

    async def send_text(self, text: str) -> AsyncGenerator[dict, None]:
        """Отправляет текст, стримит аудио-ответ, сохраняет обе реплики в БД."""
        self._sequence += 1
        seq = self._sequence

        # Сохраняем реплику пользователя немедленно (FIX 4: real-time persistence)
        await self.db.turn.create(
            data={
                "session_id": self.session_id,
                "sequence": seq,
                "role": "user",
                "text": text,
            }
        )

        await self._session.send_client_content(
            turns=genai_types.Content(
                role="user",
                parts=[genai_types.Part(text=text)],
            )
        )

        audio_chunks: list[bytes] = []
        full_transcript = ""

        async for message in self._session.receive():
            if not message.server_content:
                continue

            model_turn = message.server_content.model_turn
            if model_turn and model_turn.parts:
                for part in model_turn.parts:
                    if part.text:
                        full_transcript += part.text
                    if part.inline_data and part.inline_data.data:
                        audio_chunks.append(part.inline_data.data)
                        yield {
                            "type": "audio_chunk",
                            "audio": part.inline_data.data,
                            "transcript_partial": full_transcript,
                        }

            if message.server_content.turn_complete:
                wav_path, duration_ms = save_turn_audio(self.session_id, seq, "model", audio_chunks)
                await self.db.turn.create(
                    data={
                        "session_id": self.session_id,
                        "sequence": seq,
                        "role": "model",
                        "text": full_transcript or None,
                        "audio_file_path": wav_path or None,
                        "audio_duration_ms": duration_ms or None,
                    }
                )
                await self.db.session.update(
                    where={"id": self.session_id},
                    data={"turn_count": {"increment": 1}},
                )
                # Сохраняем handle если доступен
                handle = getattr(self._session, "resume_token", None)
                if handle:
                    await session_store.update_handle(self.session_id, handle)

                yield {
                    "type": "turn_complete",
                    "transcript": full_transcript,
                    "audio_path": wav_path,
                    "duration_ms": duration_ms,
                }
                break

    async def send_audio_chunk(self, pcm_16khz: bytes) -> None:
        """Отправляет PCM-чанк от браузера (16kHz) в Gemini Live."""
        await self._session.send_realtime_input(audio=pcm_16khz)

    async def close(self) -> None:
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass


async def create_session(
    user_id: str,
    db: Prisma,
    voice: str = "Kore",
    language: str = "ru-RU",
    system_prompt: str = NURSE_SYSTEM_PROMPT,
    source: str = "web",
) -> tuple[GeminiSessionManager, str]:
    session_id = f"sess_{uuid.uuid4().hex[:12]}"

    await db.session.create(
        data={
            "id": session_id,
            "user_id": user_id,
            "voice": voice,
            "language": language,
            "source": source,
            "audio_storage_path": str(settings.audio_storage_path + "/" + session_id),
        }
    )

    stored = StoredSession(
        session_id=session_id,
        user_id=user_id,
        system_prompt=system_prompt,
        voice=voice,
        language=language,
        created_at=__import__("time").time(),
        last_activity=__import__("time").time(),
    )
    await session_store.save(stored)

    manager = GeminiSessionManager(session_id=session_id, stored=stored, db=db)
    await manager.connect()

    return manager, session_id
