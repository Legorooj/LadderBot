"""add step field to game

Revision ID: 3844041321eb
Revises: 60f3a71a861c
Create Date: 2020-12-03 17:39:45.127738

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3844041321eb'
down_revision = '60f3a71a861c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('game', sa.Column('step', sa.Integer(), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('game', 'step')
    # ### end Alembic commands ###
