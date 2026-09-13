"""enforce at most one active link per owner

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-13

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # Partial unique index: only one row with active=true per owner_user_id.
    # Closes a TOCTOU race in create_link()/regenerate_link() (check-then-insert
    # with no DB-level guard) that a real multi-connection Postgres deployment
    # can hit under concurrent requests from the same user.
    #
    # Postgres-only (`postgresql_where=`): this app's supported production
    # target is Postgres (see infra/DEPLOYMENT.md). SQLite is dev/test-only
    # and never migrated via Alembic there — tests build their schema from
    # core.models.Base.metadata directly, whose PublicLink.__table_args__
    # carries both postgresql_where and sqlite_where so the same guard is
    # exercised in the test suite. Running this specific migration against
    # SQLite would instead create a plain (non-partial) unique index, which
    # is wrong — another reason not to run Alembic against SQLite here.
    op.create_index(
        "uq_one_active_link_per_owner",
        "public_links",
        ["owner_user_id"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_one_active_link_per_owner", table_name="public_links")
