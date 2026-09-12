"""Database schema, per the master plan's DATABASE section.

Deliberately excludes any V3+ concept (advertisers/campaigns/ad_impressions) and
deliberately excludes any column that would store sender Telegram identity.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_token() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class ReportReason(str, enum.Enum):
    HARASSMENT = "harassment"
    THREAT = "threat"
    SEXUAL = "sexual"
    SPAM = "spam"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    OPEN = "open"
    DISMISSED = "dismissed"
    ACTIONED = "actioned"
    ESCALATED = "escalated"


class Severity(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class User(Base):
    __tablename__ = "users"

    tg_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lang: Mapped[str] = mapped_column(String(5), default="uz", server_default="uz")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    blocked_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    settings: Mapped[dict] = mapped_column(JSON, default=dict)

    links: Mapped[list["PublicLink"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class PublicLink(Base):
    __tablename__ = "public_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_user_id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=new_token)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    report_count: Mapped[int] = mapped_column(Integer, default=0)

    owner: Mapped["User"] = relationship(back_populates="links")
    messages: Mapped[list["Message"]] = relationship(back_populates="link", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("public_links.id"), index=True)
    recipient_user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_user_id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    abuse_score: Mapped[int] = mapped_column(Integer, default=0)
    sender_fingerprint_hash: Mapped[str] = mapped_column(String(64), index=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    link: Mapped["PublicLink"] = relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_recipient_created", "recipient_user_id", "created_at"),
    )


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.tg_user_id"), index=True)
    sender_fingerprint_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "sender_fingerprint_hash", name="uq_block_user_fingerprint"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    reason: Mapped[str] = mapped_column(String(32))
    # Evidence snapshot captured at report time so moderators can review reported
    # content even after the recipient exercises their real right to delete it.
    body_snapshot: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ReportStatus.OPEN.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModerationAction(Base):
    __tablename__ = "moderation_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    severity: Mapped[str] = mapped_column(String(4))
    moderator: Mapped[str] = mapped_column(String(64), default="system")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.tg_user_id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    props: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
