"""Add bot_users table

Revision ID: a3d8f9b2c1e5
Revises: 42f496ca8ae8
Create Date: 2026-01-22 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a3d8f9b2c1e5'
down_revision: Union[str, Sequence[str], None] = '42f496ca8ae8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create bot_users table."""
    op.create_table('bot_users',
        sa.Column('telegram_chat_id', sa.BigInteger(), nullable=False),
        sa.Column('current_role', sa.String(length=20), nullable=False, server_default='passenger'),
        sa.Column('driver_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('driver_name', sa.String(length=100), nullable=True),
        sa.Column('car_description', sa.String(length=200), nullable=True),
        sa.Column('driver_status', sa.String(length=20), nullable=False, server_default='offline'),
        sa.Column('active_trip_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('telegram_chat_id'),
        sa.ForeignKeyConstraint(['driver_id'], ['drivers.id'], ondelete='SET NULL')
    )

    # Create index on driver_id for faster lookups
    op.create_index(op.f('ix_bot_users_driver_id'), 'bot_users', ['driver_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema - drop bot_users table."""
    op.drop_index(op.f('ix_bot_users_driver_id'), table_name='bot_users')
    op.drop_table('bot_users')
