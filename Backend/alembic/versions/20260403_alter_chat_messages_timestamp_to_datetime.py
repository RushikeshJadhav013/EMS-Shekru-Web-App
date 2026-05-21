"""Convert chat_messages.timestamp from FLOAT to DATETIME (UTC)

Revision ID: alter_chat_messages_timestamp_to_datetime
Revises: add_chat_messages
Create Date: 2026-04-03
"""

from alembic import op
from sqlalchemy import inspect


revision = "alter_chat_messages_timestamp_to_datetime"
down_revision = "add_chat_messages"
branch_labels = None
depends_on = None


def _timestamp_is_datetime() -> bool:
    if "chat_messages" not in inspect(op.get_bind()).get_table_names():
        return False
    for col in inspect(op.get_bind()).get_columns("chat_messages"):
        if col["name"] == "timestamp":
            return "datetime" in str(col["type"]).lower()
    return False


def upgrade() -> None:
    if _timestamp_is_datetime():
        return

    op.execute("ALTER TABLE chat_messages ADD COLUMN timestamp_dt DATETIME NULL")
    op.execute("UPDATE chat_messages SET timestamp_dt = FROM_UNIXTIME(timestamp)")
    op.execute("UPDATE chat_messages SET timestamp_dt = FROM_UNIXTIME(0) WHERE timestamp_dt IS NULL")
    op.execute("ALTER TABLE chat_messages DROP INDEX ix_chat_messages_chat_id_timestamp")
    op.execute("ALTER TABLE chat_messages DROP COLUMN timestamp")
    op.execute("ALTER TABLE chat_messages CHANGE timestamp_dt timestamp DATETIME NOT NULL")
    op.execute(
        "ALTER TABLE chat_messages ADD INDEX ix_chat_messages_chat_id_timestamp (chat_id, timestamp)"
    )


def downgrade() -> None:
    if not _timestamp_is_datetime():
        return

    op.execute("ALTER TABLE chat_messages ADD COLUMN timestamp_float FLOAT NULL")
    op.execute(
        "UPDATE chat_messages SET timestamp_float = UNIX_TIMESTAMP(timestamp) WHERE timestamp IS NOT NULL"
    )
    op.execute("ALTER TABLE chat_messages DROP INDEX ix_chat_messages_chat_id_timestamp")
    op.execute("ALTER TABLE chat_messages DROP COLUMN timestamp")
    op.execute("ALTER TABLE chat_messages CHANGE timestamp_float timestamp FLOAT NOT NULL")
    op.execute(
        "ALTER TABLE chat_messages ADD INDEX ix_chat_messages_chat_id_timestamp (chat_id, timestamp)"
    )
