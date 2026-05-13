import json
from typing import Any

from sqlalchemy import text

from ..db import db, get_runtime_config, row_to_dict


def list_message_logs(limit: int) -> list[dict[str, Any]]:
    max_limit = int(get_runtime_config()["max_log_limit"])
    with db() as conn:
        rows = conn.execute(
            text("select * from messages order by created_at desc limit :limit"),
            {"limit": min(limit, max_limit)},
        ).fetchall()
    items = []
    for row in rows:
        item = row_to_dict(row)
        item["sources"] = json.loads(item.pop("sources_json"))
        items.append(item)
    return items
