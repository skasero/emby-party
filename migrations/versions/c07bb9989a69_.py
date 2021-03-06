"""empty message

Revision ID: c07bb9989a69
Revises: 483a056e4a88
Create Date: 2021-01-09 22:01:25.524736

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c07bb9989a69'
down_revision = '483a056e4a88'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('room',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('roomname', sa.String(length=128), nullable=True),
    sa.Column('ticks', sa.BigInteger(), nullable=True),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('is_paused', sa.Boolean(), nullable=True),
    sa.Column('playing', sa.Boolean(), nullable=True),
    sa.Column('lastTimeUpdatedAt', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('session', sa.Column('lastTimeUpdatedAt', sa.DateTime(), nullable=True))
    op.add_column('session', sa.Column('room_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'session', 'room', ['room_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'session', type_='foreignkey')
    op.drop_column('session', 'room_id')
    op.drop_column('session', 'lastTimeUpdatedAt')
    op.drop_table('room')
    # ### end Alembic commands ###
