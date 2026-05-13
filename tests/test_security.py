import unittest

from app.security import RequestContext, create_access_token, hash_password, parse_access_token, system_context, verify_password


class SecurityTest(unittest.TestCase):
    def test_system_context_is_admin(self) -> None:
        context = system_context()

        self.assertTrue(context.is_admin)
        self.assertEqual("system", context.user_id)

    def test_user_context_is_not_admin(self) -> None:
        context = RequestContext(user_id="u1", user_name="张三", role="user", department_id=1)

        self.assertFalse(context.is_admin)

    def test_password_hash_verification(self) -> None:
        password_hash = hash_password("admin123")

        self.assertTrue(verify_password("admin123", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))

    def test_access_token_roundtrip(self) -> None:
        context = RequestContext(user_id="u1", user_name="张三", role="user", department_id=1)
        token = create_access_token(context)
        parsed = parse_access_token(token)

        self.assertIsNotNone(parsed)
        self.assertEqual("u1", parsed.user_id)
        self.assertEqual(1, parsed.department_id)


if __name__ == "__main__":
    unittest.main()
