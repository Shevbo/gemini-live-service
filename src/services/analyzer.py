"""
Пост-сессионный анализ: извлекает дневник и расходы из транскрипции.
Запускается в фоне после завершения сессии.
"""

import asyncio
import json
import logging

import httpx
from google import genai
from google.genai import types as genai_types
from prisma import Prisma

from src.config import settings

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """Ты — ассистент по анализу терапевтических диалогов.
Прочитай транскрипцию разговора пользователя с психологическим ассистентом «Медсестра»
и извлеки данные строго в JSON:

{
  "diary": {
    "mood": <1-10 или null если не определить>,
    "summary": "<1-2 предложения о чём был разговор>",
    "key_events": ["<событие 1>", ...],
    "insights": ["<инсайт 1>", ...],
    "action_items": ["<дело 1>", ...]
  },
  "expenses": [
    {
      "amount": <число>,
      "currency": "RUB",
      "category": "<еда|транспорт|здоровье|развлечения|образование|другое>",
      "description": "<что>",
      "date": "<YYYY-MM-DD или null>"
    }
  ]
}

Если расходов не упоминалось — "expenses": [].
Если не можешь определить mood — null.
Верни ТОЛЬКО JSON без markdown-блоков."""


async def analyze_session(session_id: str, user_id: str, db: Prisma) -> None:
    try:
        turns = await db.turn.find_many(
            where={"session_id": session_id},
            order={"sequence": "asc"},
        )
        if not turns:
            return

        transcript_parts = []
        for t in turns:
            if t.text:
                label = "Пользователь" if t.role == "user" else "Медсестра"
                transcript_parts.append(f"{label}: {t.text}")

        if not transcript_parts:
            return

        transcript = "\n".join(transcript_parts)

        client = genai.Client(api_key=settings.gemini_api_key)
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{ANALYSIS_PROMPT}\n\nТранскрипция:\n{transcript}",
                config=genai_types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            ),
        )

        data = json.loads(response.text)
        diary = data.get("diary", {})
        expenses = data.get("expenses", [])

        from datetime import date
        today = date.today().isoformat()

        diary_entry = await db.diaryentry.create(
            data={
                "user_id": user_id,
                "entry_date": today,
                "mood": diary.get("mood"),
                "summary": diary.get("summary"),
                "key_events": diary.get("key_events", []),
                "insights": diary.get("insights", []),
                "action_items": diary.get("action_items", []),
                "source_session_id": session_id,
            }
        )

        for exp in expenses:
            await db.expense.create(
                data={
                    "user_id": user_id,
                    "expense_date": exp.get("date") or today,
                    "amount": float(exp["amount"]),
                    "currency": exp.get("currency", "RUB"),
                    "category": exp.get("category", "другое"),
                    "description": exp.get("description"),
                    "source_session_id": session_id,
                }
            )

        await db.session.update(
            where={"id": session_id},
            data={"summary": diary.get("summary")},
        )

        await _notify_openclaw(session_id, diary_entry.id)
        logger.info("analysis_complete", session_id=session_id, diary_id=diary_entry.id)

    except Exception as e:
        logger.error("analysis_failed", session_id=session_id, error=str(e))


async def _notify_openclaw(session_id: str, diary_entry_id: int) -> None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                settings.openclaw_notify_url,
                json={
                    "type": "diary_update",
                    "session_id": session_id,
                    "diary_entry_id": diary_entry_id,
                },
            )
    except Exception as e:
        logger.warning("openclaw_notify_failed", error=str(e))
