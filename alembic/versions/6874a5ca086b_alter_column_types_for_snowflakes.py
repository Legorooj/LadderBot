"""Alter column types for snowflakes

Revision ID: 6874a5ca086b
Revises: b485da6834d9
Create Date: 2020-10-25 17:29:19.656802

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6874a5ca086b'
down_revision = 'b485da6834d9'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'player',
        'id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )
    op.alter_column(
        'game',
        'host_id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )
    op.alter_column(
        'game',
        'away_id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )
    op.alter_column(
        'game',
        'winner_id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )
    op.alter_column(
        'signup',
        'player_id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )
    op.alter_column(
        'signupmessage',
        'message_id',
        type_=sa.BigInteger,
        existing_type=sa.Integer
    )


def downgrade():
    op.alter_column(
        'player',
        'id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
    op.alter_column(
        'game',
        'host_id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
    op.alter_column(
        'game',
        'away_id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
    op.alter_column(
        'game',
        'winner_id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
    op.alter_column(
        'signup',
        'player_id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
    op.alter_column(
        'signupmessage',
        'message_id',
        type_=sa.Integer,
        existing_type=sa.BigInteger
    )
