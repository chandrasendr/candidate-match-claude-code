from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.database.db import get_db
from backend.models.job import Job
from backend.models.client import Client

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobResponse:
    @staticmethod
    def serialize(job: Job) -> dict:
        return {
            "id": job.id,
            "client_id": job.client_id,
            "client_name": job.client.name if job.client else None,
            "title": job.title,
            "location": job.location,
            "department": job.department,
            "job_url": job.job_url,
            "is_active": job.is_active,
            "found_at": job.found_at.isoformat(),
            "last_seen_at": job.last_seen_at.isoformat(),
            "is_new": job.found_at >= datetime.utcnow() - timedelta(hours=48),
        }


@router.get("/")
async def list_jobs(
    client_id: Optional[int] = Query(None),
    location: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(500, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Job)
        .options(selectinload(Job.client))
        .join(Client, Job.client_id == Client.id)
    )

    if active_only:
        query = query.where(Job.is_active == True)  # noqa: E712
        query = query.where(Client.is_active == True)  # noqa: E712

    if client_id is not None:
        query = query.where(Job.client_id == client_id)

    if location:
        query = query.where(Job.location.ilike(f"%{location}%"))

    if keyword:
        query = query.where(
            Job.title.ilike(f"%{keyword}%")
            | Job.department.ilike(f"%{keyword}%")
            | Job.location.ilike(f"%{keyword}%")
        )

    total_query = query
    query = query.order_by(Job.found_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return {
        "jobs": [JobResponse.serialize(j) for j in jobs],
        "count": len(jobs),
    }


@router.get("/stats")
async def job_stats(db: AsyncSession = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(hours=48)

    all_result = await db.execute(
        select(Job).where(Job.is_active == True)  # noqa: E712
    )
    all_jobs = all_result.scalars().all()

    new_result = await db.execute(
        select(Job).where(Job.is_active == True, Job.found_at >= cutoff)  # noqa: E712
    )
    new_jobs = new_result.scalars().all()

    return {
        "total_active": len(all_jobs),
        "new_last_48h": len(new_jobs),
    }
