"""document processing status

Revision ID: 0003_document_processing_status
Revises: 0002_add_schema_comments
Create Date: 2026-05-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_document_processing_status"
down_revision = "0002_add_schema_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("status", sa.Text(), nullable=False, server_default="uploaded"))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=False, server_default=""))
    op.add_column("documents", sa.Column("indexed_at", sa.Text(), nullable=True))
    op.execute("update documents set status = 'indexed' where chunk_count > 0")
    op.execute("comment on column documents.status is '文档处理状态：uploaded、parsing、chunking、embedding、indexed、failed'")
    op.execute("comment on column documents.error_message is '文档处理失败时的错误信息'")
    op.execute("comment on column documents.indexed_at is '文档完成向量索引的时间，UTC ISO 格式'")


def downgrade() -> None:
    op.drop_column("documents", "indexed_at")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "status")
