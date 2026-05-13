"""add schema comments

Revision ID: 0002_add_schema_comments
Revises: 0001_initial_schema
Create Date: 2026-05-12
"""

from alembic import op


revision = "0002_add_schema_comments"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


COMMENTS = [
    ("table", "documents", None, "知识库文档表，记录上传文件及入库状态相关信息"),
    ("column", "documents", "id", "文档自增主键"),
    ("column", "documents", "filename", "原始文件名"),
    ("column", "documents", "file_type", "文件类型或扩展名，例如 .pdf、.docx、.md"),
    ("column", "documents", "path", "服务端保存路径"),
    ("column", "documents", "status", "文档处理状态：uploaded、parsing、chunking、embedding、indexed、failed"),
    ("column", "documents", "error_message", "文档处理失败时的错误信息"),
    ("column", "documents", "chunk_count", "该文档切分后的片段数量"),
    ("column", "documents", "indexed_at", "文档完成向量索引的时间，UTC ISO 格式"),
    ("column", "documents", "created_at", "文档上传入库时间，UTC ISO 格式"),
    ("table", "chunks", None, "文档片段表，保存切分后的文本块及元数据"),
    ("column", "chunks", "id", "片段唯一 ID，通常由文档 ID 和片段序号生成"),
    ("column", "chunks", "document_id", "所属文档 ID，关联 documents.id"),
    ("column", "chunks", "chunk_index", "片段在文档中的序号"),
    ("column", "chunks", "text", "片段原文内容"),
    ("column", "chunks", "metadata_json", "片段元数据 JSON，例如文件名、页码、章节、片段序号"),
    ("column", "chunks", "created_at", "片段创建时间，UTC ISO 格式"),
    ("table", "conversations", None, "多轮会话表，记录一次连续问答上下文"),
    ("column", "conversations", "id", "会话唯一 ID"),
    ("column", "conversations", "title", "会话标题，默认取首个问题前若干字符"),
    ("column", "conversations", "created_at", "会话创建时间，UTC ISO 格式"),
    ("table", "messages", None, "问答消息表，记录问题、答案、召回来源和耗时"),
    ("column", "messages", "id", "消息唯一 ID"),
    ("column", "messages", "conversation_id", "所属会话 ID，关联 conversations.id"),
    ("column", "messages", "question", "用户问题"),
    ("column", "messages", "answer", "模型或本地回答生成的答案"),
    ("column", "messages", "sources_json", "检索召回片段 JSON，包含 chunk_id、score、text、metadata"),
    ("column", "messages", "latency_ms", "本次问答总耗时，单位毫秒"),
    ("column", "messages", "created_at", "消息创建时间，UTC ISO 格式"),
    ("table", "feedback", None, "用户反馈表，记录答案是否有帮助及补充意见"),
    ("column", "feedback", "id", "反馈自增主键"),
    ("column", "feedback", "message_id", "被反馈的消息 ID，关联 messages.id"),
    ("column", "feedback", "rating", "反馈类型，up 表示有帮助，down 表示需改进"),
    ("column", "feedback", "comment", "用户补充反馈说明"),
    ("column", "feedback", "created_at", "反馈创建时间，UTC ISO 格式"),
    ("table", "app_config", None, "运行时配置表，保存 chunk、topK、模型、rerank 等后台配置"),
    ("column", "app_config", "key", "配置项名称"),
    ("column", "app_config", "value", "配置项 JSON 序列化后的值"),
    ("table", "alembic_version", None, "Alembic 数据库迁移版本表"),
    ("column", "alembic_version", "version_num", "当前数据库 schema 版本号"),
]


def upgrade() -> None:
    for target_type, table, column, comment in COMMENTS:
        if target_type == "table":
            op.execute(f"comment on table {table} is '{comment}'")
        else:
            op.execute(f"comment on column {table}.{column} is '{comment}'")


def downgrade() -> None:
    for target_type, table, column, _comment in COMMENTS:
        if target_type == "table":
            op.execute(f"comment on table {table} is null")
        else:
            op.execute(f"comment on column {table}.{column} is null")
