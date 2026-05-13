import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from app.repositories.documents import list_documents
from app.repositories.feedback import create_feedback
from app.repositories.messages import list_message_logs
from app.security import RequestContext


class RepositoryTest(unittest.TestCase):
    def test_list_documents_maps_rows_to_dicts(self) -> None:
        fake_conn = _fake_connection([{"id": 1, "filename": "制度.txt"}])

        with patch("app.repositories.documents.db", _fake_db(fake_conn)):
            documents = list_documents()

        self.assertEqual([{"id": 1, "filename": "制度.txt"}], documents)

    def test_list_documents_uses_department_filter_for_non_admin(self) -> None:
        fake_conn = _fake_connection([])
        context = RequestContext(user_id="u1", user_name="张三", role="user", department_id=1)

        with patch("app.repositories.documents.db", _fake_db(fake_conn)):
            list_documents(context)

        _, params = fake_conn.execute.call_args.args
        self.assertEqual("u1", params["user_id"])
        self.assertEqual(1, params["department_id"])

    def test_create_feedback_writes_feedback_row(self) -> None:
        fake_conn = Mock()

        with patch("app.repositories.feedback.db", _fake_db(fake_conn)):
            create_feedback("m1", "up", "准确")

        self.assertTrue(fake_conn.execute.called)

    def test_list_message_logs_parses_sources_json(self) -> None:
        fake_conn = _fake_connection(
            [
                {
                    "id": "m1",
                    "question": "问题",
                    "answer": "答案",
                    "sources_json": '[{"chunk_id": "c1"}]',
                }
            ]
        )

        with (
            patch("app.repositories.messages.db", _fake_db(fake_conn)),
            patch("app.repositories.messages.get_runtime_config", return_value={"max_log_limit": 200}),
        ):
            logs = list_message_logs(10)

        self.assertEqual([{"chunk_id": "c1"}], logs[0]["sources"])


def _fake_connection(rows):
    result = Mock()
    result.fetchall.return_value = rows
    fake_conn = Mock()
    fake_conn.execute.return_value = result
    return fake_conn


def _fake_db(fake_conn):
    @contextmanager
    def manager():
        yield fake_conn

    return manager


if __name__ == "__main__":
    unittest.main()
