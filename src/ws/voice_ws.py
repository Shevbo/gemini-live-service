"""
WebSocket эндпоинт для двустороннего голосового диалога с браузера.

Протокол:
  Клиент → сервер:
    {"type": "start", "token": "<bearer>", "voice": "Kore", "language": "ru-RU"}
    {"type": "audio", "data": "<base64 PCM 16kHz>"}
    {"type": "text", "text": "<сообщение>"}
    {"type": "stop"}

  Сервер → клиент:
    {"type": "session_ready", "session_id": "..."}
    {"type": "audio", "data": "<base64 PCM 24kHz>", "transcript_partial": "..."}
    {"type": "turn_complete", "transcript": "...", "duration_ms": 0}
    {"type": "error", "message": "..."}
"""

import asyncio
import base64
import json

import structlog
from fastapi import WebSocket, WebSocketDisconnect
from prisma import Prisma

from src.auth import get_user_from_token
from src.session.manager import GeminiSessionManager, create_session

logger = structlog.get_logger()


async def handle_voice_ws(websocket: WebSocket) -> None:
    await websocket.accept()

    manager: GeminiSessionManager | None = None
    db: Prisma | None = None
    audio_buffer: list[bytes] = []

    try:
        # Первое сообщение — авторизация и старт сессии
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        init_msg = json.loads(raw)

        if init_msg.get("type") != "start":
            await websocket.send_json({"type": "error", "message": "Expected start message"})
            await websocket.close()
            return

        user = get_user_from_token(init_msg.get("token", ""))
        if not user:
            await websocket.send_json({"type": "error", "message": "Unauthorized"})
            await websocket.close()
            return

        db = Prisma()
        await db.connect()

        manager, session_id = await create_session(
            user_id=user.id,
            db=db,
            voice=init_msg.get("voice", "Kore"),
            language=init_msg.get("language", "ru-RU"),
            source="web",
        )

        await websocket.send_json({"type": "session_ready", "session_id": session_id})
        logger.info("ws_session_started", session_id=session_id, user=user.id)

        # Основной цикл
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "audio":
                # PCM 16kHz от браузера → в Gemini Live
                pcm = base64.b64decode(msg["data"])
                audio_buffer.append(pcm)
                await manager.send_audio_chunk(pcm)

            elif msg_type == "text":
                # Текстовое сообщение → стримим ответ обратно
                async for chunk in manager.send_text(msg["text"], db):
                    if chunk["type"] == "audio_chunk":
                        await websocket.send_json({
                            "type": "audio",
                            "data": base64.b64encode(chunk["audio"]).decode(),
                            "transcript_partial": chunk.get("transcript_partial", ""),
                        })
                    elif chunk["type"] == "turn_complete":
                        await websocket.send_json({
                            "type": "turn_complete",
                            "transcript": chunk.get("transcript", ""),
                            "duration_ms": chunk.get("duration_ms", 0),
                        })

            elif msg_type == "stop":
                break

    except WebSocketDisconnect:
        logger.info("ws_disconnected")
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "message": "Timeout waiting for start"})
    except Exception as e:
        logger.error("ws_error", error=str(e))
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if manager:
            await manager.close()
        if db:
            await db.disconnect()
