from typing import Any

from sqlalchemy import text

from ..db import db, row_to_dict


def list_documents() -> list[dict[str, Any]]:
    with db() as conn:
        rows = conn.execute(text("select * from documents order by created_at desc")).fetchall()
    return [row_to_dict(row) for row in rows]
