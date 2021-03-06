"""Add gamelog, remove inactive count

Revision ID: 29d69456e7ef
Revises: 21971d2083d7
Create Date: 2021-01-08 16:16:37.275215

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29d69456e7ef'
down_revision = '21971d2083d7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('gamelog',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('message', sa.String(), nullable=True),
    sa.Column('message_ts', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id')
    )
    op.drop_column('player', 'weeks_since_last_match')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('player', sa.Column('weeks_since_last_match', sa.INTEGER(), autoincrement=False, nullable=False))
    op.drop_table('gamelog')
    # ### end Alembic commands ###
