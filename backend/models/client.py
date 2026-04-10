from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.db import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    career_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    ats_platform: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="client", cascade="all, delete-orphan")  # noqa: F821


ATS_PLATFORMS = [
    "Greenhouse",
    "Lever",
    "Workday",
    "BambooHR",
    "iCIMS",
    "Taleo",
    "SmartRecruiters",
    "Jobvite",
    "ADP",
    "Successfactors",
    "Recruitee",
    "Breezy HR",
    "Custom",
    "Unknown",
]
