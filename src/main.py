"""
Gemini Live Voice Service
Голосовой терапевтический ассистент с персистентностью данных.
"""

import logging

import structlog
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

# config.py устанавливает HTTPS_PROXY/HTTP_PROXY при импорте
from src.config import settings  # noqa: F401
from src.api import voice, dialogs, diary
from src.ws.voice_ws import handle_voice_ws

logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.log_level)))

app = FastAPI(
    title="Gemini Live Voice Service",
    description="Голосовой терапевтический ассистент «Медсестра»",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.include_router(voice.router)
app.include_router(dialogs.router)
app.include_router(diary.router)


@app.websocket("/ws/voice")
async def websocket_voice(websocket: WebSocket) -> None:
    await handle_voice_ws(websocket)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "gemini-live-voice"}


# Статические файлы монтируем последними (перехватывают все остальные пути)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
