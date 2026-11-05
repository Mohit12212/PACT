"""Relational model: users, organisations, marketplace listings, partnerships and their workspace."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


ORG_TYPES = ["NGO", "College", "Startup", "Company", "Government", "Community"]
STATUSES = ["proposed", "negotiating", "active", "completed", "declined"]


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    type: Mapped[str] = mapped_column(String(20), default="NGO")
    sector: Mapped[str] = mapped_column(String(80), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    sdgs: Mapped[list] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    listings = relationship("Listing", back_populates="org", cascade="all, delete-orphan")
    users = relationship("User", back_populates="org")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    full_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(10), default="member")  # member | admin
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    org = relationship("Organization", back_populates="users")


class Listing(Base):
    """A single need or offer: the unit the marketplace and matching engine work on."""
    __tablename__ = "listings"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(5), index=True)  # need | offer
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    sdgs: Mapped[list] = mapped_column(JSON, default=list)
    remote_ok: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | filled
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)
    embed_model: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    org = relationship("Organization", back_populates="listings")

    @property
    def text(self) -> str:
        return f"{self.title}. {self.description} {' '.join(self.tags or [])}"


class Partnership(Base):
    __tablename__ = "partnerships"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_a_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)  # initiator
    org_b_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="proposed", index=True)
    match_score: Mapped[float] = mapped_column(Float, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    org_a = relationship("Organization", foreign_keys=[org_a_id])
    org_b = relationship("Organization", foreign_keys=[org_b_id])
    milestones = relationship("Milestone", cascade="all, delete-orphan", order_by="Milestone.id")
    metrics = relationship("ImpactMetric", cascade="all, delete-orphan", order_by="ImpactMetric.id")
    messages = relationship("Message", cascade="all, delete-orphan", order_by="Message.id")
    reviews = relationship("Review", cascade="all, delete-orphan")


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    partnership_id: Mapped[int] = mapped_column(ForeignKey("partnerships.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due: Mapped[str] = mapped_column(String(10), default="")
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class ImpactMetric(Base):
    __tablename__ = "impact_metrics"
    id: Mapped[int] = mapped_column(primary_key=True)
    partnership_id: Mapped[int] = mapped_column(ForeignKey("partnerships.id", ondelete="CASCADE"), index=True)
    sdg: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(30), default="")
    evidence_url: Mapped[str] = mapped_column(String(500), default="")
    verification_status: Mapped[str] = mapped_column(String(20), default="self_reported")
    verification_note: Mapped[str] = mapped_column(Text, default="")
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    partnership_id: Mapped[int] = mapped_column(ForeignKey("partnerships.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    user = relationship("User")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("partnership_id", "reviewer_org_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    partnership_id: Mapped[int] = mapped_column(ForeignKey("partnerships.id", ondelete="CASCADE"))
    reviewer_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    reviewee_org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(300))
    link: Mapped[str] = mapped_column(String(100), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Setting(Base):
    __tablename__ = "settings"
    k: Mapped[str] = mapped_column(String(40), primary_key=True)
    v: Mapped[str] = mapped_column(Text, default="")
