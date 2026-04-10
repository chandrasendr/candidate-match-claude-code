import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.database.db import get_db
from backend.models.client import Client, ATS_PLATFORMS

router = APIRouter(prefix="/clients", tags=["clients"])


class ClientCreate(BaseModel):
    name: str
    career_url: str
    ats_platform: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    career_url: Optional[str] = None
    ats_platform: Optional[str] = None
    city: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    id: int
    name: str
    career_url: str
    ats_platform: Optional[str]
    city: Optional[str]
    notes: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_model(cls, obj: Client) -> "ClientResponse":
        return cls(
            id=obj.id,
            name=obj.name,
            career_url=obj.career_url,
            ats_platform=obj.ats_platform,
            city=obj.city,
            notes=obj.notes,
            is_active=obj.is_active,
            created_at=obj.created_at.isoformat(),
            updated_at=obj.updated_at.isoformat(),
        )


@router.get("/ats-platforms")
async def get_ats_platforms():
    return {"platforms": ATS_PLATFORMS}


@router.get("/")
async def list_clients(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    query = select(Client)
    if active_only:
        query = query.where(Client.is_active == True)  # noqa: E712
    query = query.order_by(Client.name)
    result = await db.execute(query)
    clients = result.scalars().all()
    return [ClientResponse.from_orm_model(c) for c in clients]


@router.post("/", status_code=201)
async def create_client(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(
        name=data.name,
        career_url=data.career_url,
        ats_platform=data.ats_platform,
        city=data.city,
        notes=data.notes,
        is_active=data.is_active,
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return ClientResponse.from_orm_model(client)


@router.get("/{client_id}")
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse.from_orm_model(client)


@router.put("/{client_id}")
async def update_client(client_id: int, data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if data.name is not None:
        client.name = data.name
    if data.career_url is not None:
        client.career_url = data.career_url
    if data.ats_platform is not None:
        client.ats_platform = data.ats_platform
    if data.city is not None:
        client.city = data.city
    if data.notes is not None:
        client.notes = data.notes
    if data.is_active is not None:
        client.is_active = data.is_active

    await db.commit()
    await db.refresh(client)
    return ClientResponse.from_orm_model(client)


@router.delete("/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(client)
    await db.commit()


@router.post("/import/csv", status_code=201)
async def import_clients_csv(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    required = {"name", "career_url"}
    if not required.issubset({f.lower() for f in (reader.fieldnames or [])}):
        raise HTTPException(
            status_code=400,
            detail="CSV must have columns: name, career_url (optional: ats_platform, city, notes, is_active)",
        )

    created = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        row_lower = {k.lower().strip(): v.strip() for k, v in row.items() if k}
        name = row_lower.get("name", "").strip()
        career_url = row_lower.get("career_url", "").strip()

        if not name or not career_url:
            skipped += 1
            errors.append(f"Row {i}: missing name or career_url")
            continue

        is_active_raw = row_lower.get("is_active", "true").lower()
        is_active = is_active_raw not in ("false", "0", "no")

        client = Client(
            name=name,
            career_url=career_url,
            ats_platform=row_lower.get("ats_platform") or None,
            city=row_lower.get("city") or None,
            notes=row_lower.get("notes") or None,
            is_active=is_active,
        )
        db.add(client)
        created += 1

    await db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}
