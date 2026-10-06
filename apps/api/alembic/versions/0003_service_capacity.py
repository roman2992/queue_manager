from alembic import op
import sqlalchemy as sa

revision = "0003_service_capacity"
down_revision = "0002_ticket_call_tracking"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "services",
        sa.Column(
            "capacity",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade():
    op.drop_column("services", "capacity")
