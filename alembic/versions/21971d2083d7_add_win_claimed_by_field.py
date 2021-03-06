"""add win_claimed_by field

Revision ID: 21971d2083d7
Revises: a422e8412db0
Create Date: 2020-12-17 18:26:49.572496

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21971d2083d7'
down_revision = 'a422e8412db0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('game', sa.Column('win_claimed_by', sa.BigInteger(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('game', 'win_claimed_by')
    # ### end Alembic commands ###
