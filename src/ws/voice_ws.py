"""
WebSocket эндпоинт для двустороннего голосового диалога с браузера.

Протокол:
  Клиент → сервер:
    {"type": "start", "token": "<bearer>", "voice": "Kore", "language": "ru-RU"}
    {"type": "audio", "data": "<base64 PCM 16kHz>"}
    {"type": "stop"}

  Сервер → клиент:
    {"type": "session_ready", "session_id": "..."}
    {"type": "audio", "data": "<base64 PCM 24kHz>"}
    {"type": "turn_complete", "transcript": "..."}
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

        stop_event = asyncio.Event()

        # Задача 1: браузер → Gemini (аудио от микрофона)
        async def browser_to_gemini() -> None:
            while not stop_event.is_set():
                try:
                    raw = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                except WebSocketDisconnect:
                    break

                msg = json.loads(raw)
                if msg.get("type") == "audio":
                    pcm = base64.b64decode(msg["data"])
                    await manager.send_audio_chunk(pcm)
                elif msg.get("type") == "stop":
                    break

            stop_event.set()

        # Задача 2: Gemini → браузер (аудио-ответы)
        async def gemini_to_browser() -> None:
            async for chunk in manager.receive_responses():
                if stop_event.is_set():
                    break
                if chunk["type"] == "audio_chunk":
                    await websocket.send_json({
                        "type": "audio",
                        "data": base64.b64encode(chunk["audio"]).decode(),
                    })
                elif chunk["type"] == "turn_complete":
                    await websocket.send_json({
                        "type": "turn_complete",
                        "transcript": chunk.get("transcript", ""),
                    })

        t1 = asyncio.create_task(browser_to_gemini())
        t2 = asyncio.create_task(gemini_to_browser())

        # Ждём пока одна из задач завершится
        done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        stop_event.set()
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    except asyncio.TimeoutError:
        try:
            await websocket.send_json({"type": "error", "message": "Timeout waiting for start"})
        except Exception:
            pass
    except WebSocketDisconnect:
        logger.info("ws_disconnected")
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
