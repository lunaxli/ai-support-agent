"""Add support tickets and staff roles.

Revision ID: 4ee3ac912dc1
Revises: fe56fa70289e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "4ee3ac912dc1"
down_revision = "fe56fa70289e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user", sa.Column("is_support_agent", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "support_ticket",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_support_ticket_owner_id", "support_ticket", ["owner_id"])
    op.create_index("ix_support_ticket_status", "support_ticket", ["status"])
    op.create_table(
        "support_analysis",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("support_ticket.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(120)),
        sa.Column("category", sa.String(24)),
        sa.Column("priority", sa.String(12)),
        sa.Column("summary", sa.Text()),
        sa.Column("risk_flags", JSONB(), nullable=False),
        sa.Column("route", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(32)),
        sa.Column("draft", sa.Text()),
        sa.Column("sources", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_support_analysis_ticket_id", "support_analysis", ["ticket_id"])
    op.create_table(
        "support_review",
        sa.Column("analysis_id", sa.Uuid(), sa.ForeignKey("support_analysis.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("decision", sa.String(12), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("final_reply", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "support_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("support_ticket.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("user.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("details", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_support_log_ticket_id", "support_log", ["ticket_id"])


def downgrade():
    op.drop_table("support_log")
    op.drop_table("support_review")
    op.drop_table("support_analysis")
    op.drop_table("support_ticket")
    op.drop_column("user", "is_support_agent")

