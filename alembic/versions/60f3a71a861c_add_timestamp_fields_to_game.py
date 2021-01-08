"""add timestamp fields to game

Revision ID: 60f3a71a861c
Revises: 982673b06691
Create Date: 2020-12-03 17:05:54.800740

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60f3a71a861c'
down_revision = '982673b06691'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('game', sa.Column('opened_ts', sa.DateTime(), nullable=False))
    op.add_column('game', sa.Column('started_ts', sa.DateTime(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('game', 'started_ts')
    op.drop_column('game', 'opened_ts')
    # ### end Alembic commands ###
