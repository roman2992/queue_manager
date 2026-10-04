from alembic import op
import sqlalchemy as sa
revision='0001_initial'; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('users',sa.Column('id',sa.Integer,primary_key=True),sa.Column('phone',sa.String(32),nullable=False,unique=True),sa.Column('password_hash',sa.Text,nullable=False),sa.Column('role',sa.String(16),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now()))
    op.create_index('ix_users_phone','users',['phone'])
    op.create_table('businesses',sa.Column('id',sa.Integer,primary_key=True),sa.Column('owner_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('name',sa.String(160),nullable=False),sa.Column('address',sa.String(300)),sa.Column('latitude',sa.Float),sa.Column('longitude',sa.Float),sa.Column('is_open',sa.Boolean,server_default=sa.true(),nullable=False))
    op.create_index('ix_businesses_owner_id','businesses',['owner_id'])
    op.create_table('services',sa.Column('id',sa.Integer,primary_key=True),sa.Column('business_id',sa.Integer,sa.ForeignKey('businesses.id'),nullable=False),sa.Column('name',sa.String(160),nullable=False),sa.Column('avg_duration_minutes',sa.Integer,server_default='30',nullable=False),sa.Column('active',sa.Boolean,server_default=sa.true(),nullable=False))
    op.create_index('ix_services_business_id','services',['business_id'])
    op.create_table('queues',sa.Column('id',sa.Integer,primary_key=True),sa.Column('service_id',sa.Integer,sa.ForeignKey('services.id'),nullable=False),sa.Column('name',sa.String(160),nullable=False),sa.Column('is_open',sa.Boolean,server_default=sa.true(),nullable=False),sa.Column('next_sequence',sa.Integer,server_default='1',nullable=False))
    op.create_index('ix_queues_service_id','queues',['service_id'])
    op.create_table('queue_tickets',sa.Column('id',sa.Integer,primary_key=True),sa.Column('queue_id',sa.Integer,sa.ForeignKey('queues.id'),nullable=False),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('queue_sequence',sa.Integer,nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column('check_in_at',sa.DateTime(timezone=True)),sa.Column('called_at',sa.DateTime(timezone=True)),sa.Column('service_started_at',sa.DateTime(timezone=True)),sa.Column('completed_at',sa.DateTime(timezone=True)),sa.Column('expires_at',sa.DateTime(timezone=True)),sa.Column('resolved_at',sa.DateTime(timezone=True)),sa.Column('resolved_reason',sa.String(32)))
    op.create_index('ix_queue_tickets_queue_id','queue_tickets',['queue_id']); op.create_index('ix_queue_tickets_user_id','queue_tickets',['user_id']); op.create_index('ix_queue_tickets_status','queue_tickets',['status'])
def downgrade():
    op.drop_table('queue_tickets'); op.drop_table('queues'); op.drop_table('services'); op.drop_table('businesses'); op.drop_table('users')
