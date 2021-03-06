"""rename fields

Revision ID: 9a59a8b4048b
Revises: 2c3efce66502
Create Date: 2021-01-18 16:37:56.849056

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a59a8b4048b'
down_revision = '2c3efce66502'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('game', 'winner', new_column_name='winner_id')
    op.alter_column('game', 'host', new_column_name='host_id')
    op.alter_column('game', 'away', new_column_name='away_id')
    op.alter_column('signup', 'signup', new_column_name='signup_id')
    op.alter_column('signup', 'player', new_column_name='player_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('game', 'winner_id', new_column_name='winner')
    op.alter_column('game', 'host_id', new_column_name='host')
    op.alter_column('game', 'away_id', new_column_name='away')
    op.alter_column('signup', 'signup_id', new_column_name='signup')
    op.alter_column('signup', 'player_id', new_column_name='player')
    # ### end Alembic commands ###
