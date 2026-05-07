from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from prisma import Prisma

from src.auth import User, get_current_user
from src.api.voice import get_db

router = APIRouter(prefix="/v1/diary", tags=["diary"])


@router.get("/entries")
async def list_entries(
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    where: dict = {"user_id": user.id}
    if date_from:
        where.setdefault("entry_date", {})["gte"] = date_from.isoformat()
    if date_to:
        where.setdefault("entry_date", {})["lte"] = date_to.isoformat()

    total = await db.diaryentry.count(where=where)
    entries = await db.diaryentry.find_many(
        where=where,
        skip=(page - 1) * per_page,
        take=per_page,
        order={"entry_date": "desc"},
    )

    return {
        "total": total,
        "page": page,
        "items": [
            {
                "id": e.id,
                "entry_date": e.entry_date.date().isoformat(),
                "mood": e.mood,
                "summary": e.summary,
                "key_events": e.key_events,
                "insights": e.insights,
                "action_items": e.action_items,
                "source_session_id": e.source_session_id,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
    }


@router.delete("/entries/{entry_id}")
async def delete_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    entry = await db.diaryentry.find_first(where={"id": entry_id, "user_id": user.id})
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    await db.diaryentry.delete(where={"id": entry_id})
    return {"status": "deleted", "id": entry_id}


@router.get("/expenses")
async def list_expenses(
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Prisma = Depends(get_db),
) -> dict:
    where: dict = {"user_id": user.id}
    if date_from:
        where.setdefault("expense_date", {})["gte"] = date_from.isoformat()
    if date_to:
        where.setdefault("expense_date", {})["lte"] = date_to.isoformat()
    if category:
        where["category"] = category

    total = await db.expense.count(where=where)
    expenses = await db.expense.find_many(
        where=where,
        skip=(page - 1) * per_page,
        take=per_page,
        order={"expense_date": "desc"},
    )

    # Суммы по категориям
    all_for_totals = await db.expense.find_many(where={"user_id": user.id, **({
        "expense_date": where["expense_date"]} if "expense_date" in where else {})})
    totals: dict[str, float] = {}
    for e in all_for_totals:
        totals[e.category] = totals.get(e.category, 0.0) + e.amount

    return {
        "total": total,
        "page": page,
        "totals": totals,
        "items": [
            {
                "id": e.id,
                "expense_date": e.expense_date.date().isoformat(),
                "amount": e.amount,
                "currency": e.currency,
                "category": e.category,
                "description": e.description,
                "source_session_id": e.source_session_id,
            }
            for e in expenses
        ],
    }
