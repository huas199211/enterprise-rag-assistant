from sqlalchemy import text

from ..db import db, utc_now


def create_feedback(message_id: str, rating: str, comment: str) -> None:
    with db() as conn:
        conn.execute(
            text("insert into feedback(message_id, rating, comment, created_at) values(:message_id, :rating, :comment, :created_at)"),
            {
                "message_id": message_id,
                "rating": rating,
                "comment": comment,
                "created_at": utc_now(),
            },
        )
