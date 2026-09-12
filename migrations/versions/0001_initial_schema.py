"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-12

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("tg_user_id", sa.BigInteger(), primary_key=True),
        sa.Column("lang", sa.String(length=5), nullable=False, server_default="uz"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_bot", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "public_links",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger(), sa.ForeignKey("users.tg_user_id"), nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("report_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_public_links_owner_user_id", "public_links", ["owner_user_id"])
    op.create_index("ix_public_links_token", "public_links", ["token"], unique=True)

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("link_id", sa.Integer(), sa.ForeignKey("public_links.id"), nullable=False),
        sa.Column("recipient_user_id", sa.BigInteger(), sa.ForeignKey("users.tg_user_id"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("abuse_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sender_fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_messages_link_id", "messages", ["link_id"])
    op.create_index("ix_messages_recipient_user_id", "messages", ["recipient_user_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index("ix_messages_sender_fingerprint_hash", "messages", ["sender_fingerprint_hash"])
    op.create_index("ix_messages_recipient_created", "messages", ["recipient_user_id", "created_at"])

    op.create_table(
        "blocks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_user_id"), nullable=False),
        sa.Column("sender_fingerprint_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "sender_fingerprint_hash", name="uq_block_user_fingerprint"),
    )
    op.create_index("ix_blocks_user_id", "blocks", ["user_id"])
    op.create_index("ix_blocks_sender_fingerprint_hash", "blocks", ["sender_fingerprint_hash"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("body_snapshot", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reports_message_id", "reports", ["message_id"])

    op.create_table(
        "moderation_actions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=4), nullable=False),
        sa.Column("moderator", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_moderation_actions_target", "moderation_actions", ["target"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.tg_user_id"), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("props", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_name", "events", ["name"])
    op.create_index("ix_events_created_at", "events", ["created_at"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("moderation_actions")
    op.drop_table("reports")
    op.drop_table("blocks")
    op.drop_table("messages")
    op.drop_table("public_links")
    op.drop_table("users")
