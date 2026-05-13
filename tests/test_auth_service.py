import unittest
from unittest.mock import patch

from app.services.auth_service import current_user, login
from app.security import RequestContext


class AuthServiceTest(unittest.TestCase):
    def test_login_returns_token_and_permissions(self) -> None:
        user = {"id": "u1", "name": "张三", "role": "user", "department_id": 1}

        with (
            patch("app.services.auth_service.authenticate_user", return_value=user),
            patch("app.services.auth_service.user_permissions", return_value=["chat:use"]),
            patch("app.services.auth_service.write_audit_log"),
        ):
            result = login("zhangsan", "password")

        self.assertEqual("bearer", result["token_type"])
        self.assertIn("access_token", result)
        self.assertEqual(["chat:use"], result["permissions"])

    def test_login_rejects_invalid_credentials(self) -> None:
        with patch("app.services.auth_service.authenticate_user", return_value=None):
            with self.assertRaises(ValueError):
                login("missing", "wrong")

    def test_current_user_returns_context_and_permissions(self) -> None:
        context = RequestContext("u1", "张三", "user", 1)

        with patch("app.services.auth_service.user_permissions", return_value=["chat:use"]):
            result = current_user(context)

        self.assertEqual("u1", result["id"])
        self.assertEqual(["chat:use"], result["permissions"])


if __name__ == "__main__":
    unittest.main()
