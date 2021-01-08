"""Initial migration

Revision ID: 76d3ace6e04e
Revises: 
Create Date: 2020-10-23 19:06:47.961273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '76d3ace6e04e'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('game',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('host_id', sa.Integer(), nullable=False),
    sa.Column('away_id', sa.Integer(), nullable=False),
    sa.Column('winner_id', sa.Integer(), nullable=True),
    sa.Column('is_complete', sa.Boolean(), nullable=True),
    sa.Column('host_step', sa.Integer(), nullable=False),
    sa.Column('away_step', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_table('player',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=16), nullable=True),
    sa.Column('ign', sa.String(), nullable=True),
    sa.Column('steam_name', sa.String(), nullable=True),
    sa.Column('weeks_since_last_match', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_table('signup',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('signup_id', sa.Integer(), nullable=False),
    sa.Column('player_id', sa.Integer(), nullable=False),
    sa.Column('mobile', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.create_table('signupmessage',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('message_id', sa.Integer(), nullable=False),
    sa.Column('signups_open', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id'),
    sa.UniqueConstraint('message_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('signupmessage')
    op.drop_table('signup')
    op.drop_table('player')
    op.drop_table('game')
    # ### end Alembic commands ###
