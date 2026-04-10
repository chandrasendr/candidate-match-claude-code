import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.db import get_db
from backend.models.client import Client
from backend.models.scrape_log import ScrapeLog
from backend.services.scraper import run_scrape_job

router = APIRouter(prefix="/scraper", tags=["scraper"])

# Simple in-memory tracking of running scrape tasks
_active_tasks: dict[str, asyncio.Task] = {}


class ScrapeRequest(BaseModel):
    client_ids: Optional[list[int]] = None  # None = scrape all active


class ScrapeLogResponse:
    @staticmethod
    def serialize(log: ScrapeLog) -> dict:
        return {
            "id": log.id,
            "client_id": log.client_id,
            "status": log.status,
            "jobs_found": log.jobs_found,
            "jobs_new": log.jobs_new,
            "used_claude": log.used_claude,
            "error_message": log.error_message,
            "started_at": log.started_at.isoformat(),
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
        }


@router.post("/run")
async def trigger_scrape(
    data: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a scrape run. Returns immediately; scraping happens in background."""
    if data.client_ids:
        # Validate all client IDs exist
        result = await db.execute(
            select(Client).where(Client.id.in_(data.client_ids))
        )
        found = {c.id for c in result.scalars().all()}
        missing = set(data.client_ids) - found
        if missing:
            raise HTTPException(status_code=404, detail=f"Clients not found: {missing}")

    task_key = "all" if not data.client_ids else ",".join(str(i) for i in sorted(data.client_ids))

    if task_key in _active_tasks and not _active_tasks[task_key].done():
        raise HTTPException(status_code=409, detail="A scrape is already running for these clients")

    async def _run():
        from backend.database.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await run_scrape_job(session, data.client_ids)

    task = asyncio.create_task(_run())
    _active_tasks[task_key] = task

    return {
        "message": "Scrape started",
        "task_key": task_key,
        "client_ids": data.client_ids,
    }


@router.get("/status")
async def scrape_status():
    """Return status of active scrape tasks."""
    statuses = {}
    for key, task in _active_tasks.items():
        if task.done():
            exc = task.exception()
            statuses[key] = {"running": False, "error": str(exc) if exc else None}
        else:
            statuses[key] = {"running": True, "error": None}
    return statuses


@router.get("/logs")
async def get_scrape_logs(
    client_id: Optional[int] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    query = select(ScrapeLog).order_by(ScrapeLog.started_at.desc()).limit(limit)
    if client_id:
        query = query.where(ScrapeLog.client_id == client_id)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [ScrapeLogResponse.serialize(l) for l in logs]
