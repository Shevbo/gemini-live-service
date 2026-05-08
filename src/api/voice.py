import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from prisma import Prisma

from src.auth import User, get_current_user
from src.session.manager import GeminiSessionManager, create_session
from src.session.store import session_store
from src.services.analyzer import analyze_session

router = APIRouter(prefix="/v1/session", tags=["voice"])

# Активные менеджеры сессий (в памяти процесса, сессии в Redis)
_managers: dict[str, GeminiSessionManager] = {}


async def get_db() -> Prisma:
    db = Prisma()
    await db.connect()
    try:
        yield db
    finally:
        await db.disconnect()


class StartRequest(BaseModel):
    voice: str = "Kore"
    language: str = "ru-RU"
    system_prompt: str | None = None
    source: str = "web"


class SendTextRequest(BaseModel):
    text: str


@router.post("/start")
async def start_session(
    req: StartRequest,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    manager, session_id = await create_session(
        user_id=user.id,
        db=db,
        voice=req.voice,
        language=req.language,
        system_prompt=req.system_prompt or None,
        source=req.source,
    )
    _managers[session_id] = manager
    return {"session_id": session_id, "status": "created"}


@router.post("/{session_id}/send")
async def send_text(
    session_id: str,
    req: SendTextRequest,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> StreamingResponse:
    manager = _managers.get(session_id)
    if not manager:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    import json
    import base64

    async def event_stream():
        async for chunk in manager.send_text(req.text, db):
            if chunk["type"] == "audio_chunk":
                payload = {
                    "type": "audio_chunk",
                    "audio_b64": base64.b64encode(chunk["audio"]).decode(),
                    "transcript_partial": chunk.get("transcript_partial", ""),
                }
            else:
                payload = {
                    "type": "turn_complete",
                    "transcript": chunk.get("transcript", ""),
                    "duration_ms": chunk.get("duration_ms", 0),
                }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{session_id}/stop")
async def stop_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    manager = _managers.pop(session_id, None)
    if manager:
        await manager.close()

    await db.session.update(
        where={"id": session_id},
        data={"status": "completed", "endedAt": __import__("datetime").datetime.utcnow()},
    )
    await session_store.delete(session_id)

    # Анализ в фоне
    asyncio.create_task(analyze_session(session_id, user.id, db))

    return {"session_id": session_id, "status": "completed"}


@router.get("/{session_id}/audio/{filename}")
async def get_audio(
    session_id: str,
    filename: str,
    user: User = Depends(get_current_user),
) -> FileResponse:
    from pathlib import Path
    from src.config import settings

    path = Path(settings.audio_storage_path) / session_id / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file not found")
    return FileResponse(str(path), media_type="audio/wav")
