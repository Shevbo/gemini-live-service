from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Prisma

from src.auth import User, get_current_user
from src.api.voice import get_db

router = APIRouter(prefix="/v1/dialogs", tags=["dialogs"])


@router.get("")
async def list_dialogs(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    where: dict = {"userId": user.id}
    if status:
        where["status"] = status

    total = await db.session.count(where=where)
    sessions = await db.session.find_many(
        where=where,
        skip=(page - 1) * per_page,
        take=per_page,
        order={"createdAt": "desc"},
    )

    items = [
        {
            "id": s.id,
            "created_at": s.created_at.isoformat(),
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "status": s.status,
            "source": s.source,
            "turn_count": s.turn_count,
            "summary": s.summary,
            "has_audio": bool(s.audio_storage_path),
        }
        for s in sessions
    ]

    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.get("/{session_id}")
async def get_dialog(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    session = await db.session.find_first(
        where={"id": session_id, "userId": user.id},
        include={"turns": True},
    )
    if not session:
        raise HTTPException(status_code=404, detail="Dialog not found")

    turns = [
        {
            "sequence": t.sequence,
            "role": t.role,
            "text": t.text,
            "audio_url": f"/v1/session/{session_id}/audio/{t.audio_file_path.split('/')[-1]}"
            if t.audio_file_path
            else None,
            "audio_duration_ms": t.audio_duration_ms,
            "created_at": t.created_at.isoformat(),
        }
        for t in (session.turns or [])
    ]

    return {
        "session": {
            "id": session.id,
            "created_at": session.created_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "status": session.status,
            "voice": session.voice,
            "turn_count": session.turn_count,
            "summary": session.summary,
        },
        "turns": turns,
    }


@router.delete("/{session_id}")
async def delete_dialog(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    session = await db.session.find_first(where={"id": session_id, "userId": user.id})
    if not session:
        raise HTTPException(status_code=404, detail="Dialog not found")

    import shutil
    from pathlib import Path
    from src.config import settings

    audio_dir = Path(settings.audio_storage_path) / session_id
    deleted_files = 0
    if audio_dir.exists():
        deleted_files = len(list(audio_dir.glob("*.wav")))
        shutil.rmtree(audio_dir)

    await db.session.delete(where={"id": session_id})

    return {"status": "deleted", "session_id": session_id, "deleted_audio_files": deleted_files}
