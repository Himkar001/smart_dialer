"""Initial database schema — all tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enums
    op.execute("CREATE TYPE agentstate AS ENUM ('OFFLINE','AVAILABLE','RESERVED','DIALING','CONNECTED','WRAP_UP','PAUSED')")
    op.execute("CREATE TYPE campaignmode AS ENUM ('PROGRESSIVE','PREDICTIVE')")
    op.execute("CREATE TYPE campaignstate AS ENUM ('DRAFT','ACTIVE','PAUSED','COMPLETED')")
    op.execute("CREATE TYPE providertype AS ENUM ('PROVIDER_A','PROVIDER_B')")
    op.execute("CREATE TYPE borrowerstate AS ENUM ('PENDING','RESERVED','CALLED','COMPLETED','EXHAUSTED')")
    op.execute("CREATE TYPE callstate AS ENUM ('QUEUED','RESERVED','INITIATED','RINGING','ANSWERED','CONNECTED','COMPLETED','FAILED','CANCELLED')")

    # campaigns
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("mode", sa.Enum("PROGRESSIVE", "PREDICTIVE", name="campaignmode"), nullable=False),
        sa.Column("state", sa.Enum("DRAFT", "ACTIVE", "PAUSED", "COMPLETED", name="campaignstate"), nullable=False, server_default="DRAFT"),
        sa.Column("provider", sa.Enum("PROVIDER_A", "PROVIDER_B", name="providertype"), nullable=False, server_default="PROVIDER_A"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # agents
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("state", sa.Enum("OFFLINE","AVAILABLE","RESERVED","DIALING","CONNECTED","WRAP_UP","PAUSED", name="agentstate"), nullable=False, server_default="OFFLINE"),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agents_state_campaign", "agents", ["state", "campaign_id"])
    op.create_index("ix_agents_heartbeat", "agents", ["heartbeat_at"])

    # borrowers
    op.create_table(
        "borrowers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("state", sa.Enum("PENDING","RESERVED","CALLED","COMPLETED","EXHAUSTED", name="borrowerstate"), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_borrowers_campaign_state", "borrowers", ["campaign_id", "state"])

    # calls
    op.create_table(
        "calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("borrowers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("state", sa.Enum("QUEUED","RESERVED","INITIATED","RINGING","ANSWERED","CONNECTED","COMPLETED","FAILED","CANCELLED", name="callstate"), nullable=False, server_default="QUEUED"),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_call_id", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_calls_state_campaign", "calls", ["state", "campaign_id"])
    op.create_index("ix_calls_agent", "calls", ["agent_id"])

    # call_events
    op.create_table(
        "call_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("calls.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("raw_payload", postgresql.JSONB(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("call_events")
    op.drop_table("calls")
    op.drop_table("borrowers")
    op.drop_table("agents")
    op.drop_table("campaigns")
    op.execute("DROP TYPE IF EXISTS callstate")
    op.execute("DROP TYPE IF EXISTS borrowerstate")
    op.execute("DROP TYPE IF EXISTS providertype")
    op.execute("DROP TYPE IF EXISTS campaignstate")
    op.execute("DROP TYPE IF EXISTS campaignmode")
    op.execute("DROP TYPE IF EXISTS agentstate")
