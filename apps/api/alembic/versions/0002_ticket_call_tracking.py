from alembic import op
import sqlalchemy as sa

revision = "0002_ticket_call_tracking"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "queue_tickets",
        sa.Column(
            "call_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "queue_tickets",
        sa.Column(
            "skip_once",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("queue_tickets", "skip_once")
    op.drop_column("queue_tickets", "call_attempts")
