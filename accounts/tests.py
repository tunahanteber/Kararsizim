from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()

VALID = {
    "email": "ali@example.com",
    "username": "ali_k",
    "password1": "Sagl4m-Parola!",
    "password2": "Sagl4m-Parola!",
}


class SignUpTests(TestCase):
    def post(self, **overrides):
        return self.client.post(reverse("signup"), {**VALID, **overrides})

    def test_signup_creates_user_and_logs_in(self):
        r = self.post()
        self.assertRedirects(r, "/")
        user = User.objects.get(email="ali@example.com")
        self.assertEqual(user.username, "ali_k")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_signup_normalizes_case(self):
        self.post(email="Ali@Example.com", username="Ali_K")
        user = User.objects.get()
        self.assertEqual((user.email, user.username), ("ali@example.com", "ali_k"))

    def test_duplicate_email_rejected(self):
        self.post()
        self.client.logout()
        r = self.post(username="baska_ad", email="ALI@example.com")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "zaten bir hesap var")
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_username_case_insensitive_rejected(self):
        self.post()
        self.client.logout()
        r = self.post(email="b@example.com", username="ALI_K")
        self.assertContains(r, "alınmış")
        self.assertEqual(User.objects.count(), 1)

    def test_reserved_usernames_rejected(self):
        for name in ["admin", "yeni", "giris", "kayit", "cikis", "api", "static", "kararsizim", "u", "a"]:
            r = self.post(username=name)
            self.assertEqual(r.status_code, 200, name)
        self.assertEqual(User.objects.count(), 0)

    def test_invalid_usernames_rejected(self):
        for name in ["ab", "türkçe", "bosluk var", "x" * 21, "a-b"]:
            r = self.post(username=name)
            self.assertEqual(r.status_code, 200, name)
        self.assertEqual(User.objects.count(), 0)

    def test_password_mismatch_rejected(self):
        r = self.post(password2="Baska-Parola1!")
        self.assertContains(r, "Parolalar eşleşmiyor")

    def test_signup_redirects_to_next(self):
        r = self.client.post(reverse("signup") + "?next=/yeni/", {**VALID, "next": "/yeni/"})
        self.assertRedirects(r, "/yeni/", fetch_redirect_response=False)

    def test_signup_rejects_external_next(self):
        r = self.client.post(reverse("signup"), {**VALID, "next": "https://evil.example/"})
        self.assertRedirects(r, "/", fetch_redirect_response=False)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ali@example.com", username="ali_k", password="Sagl4m-Parola!"
        )

    def test_login_with_email(self):
        r = self.client.post(reverse("login"), {"username": "Ali@Example.com", "password": "Sagl4m-Parola!"})
        self.assertRedirects(r, "/")

    def test_login_with_username(self):
        for name in ("ali_k", "Ali_K", "@ali_k"):
            self.client.logout()
            r = self.client.post(reverse("login"), {"username": name, "password": "Sagl4m-Parola!"})
            self.assertRedirects(r, "/", fetch_redirect_response=False)
            self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_unknown_username_generic_error(self):
        r = self.client.post(reverse("login"), {"username": "yok_kimse", "password": "Sagl4m-Parola!"})
        self.assertContains(r, "hatalı")
        r2 = self.client.post(reverse("login"), {"username": "ali_k", "password": "yanlis"})
        self.assertContains(r2, "hatalı")  # aynı mesaj: kullanıcı adı var mı yok mu belli olmaz

    def test_login_wrong_password(self):
        r = self.client.post(reverse("login"), {"username": "ali@example.com", "password": "yanlis"})
        self.assertContains(r, "veya parola hatalı")

    def test_login_next(self):
        r = self.client.post(
            reverse("login") + "?next=/yeni/",
            {"username": "ali@example.com", "password": "Sagl4m-Parola!", "next": "/yeni/"},
        )
        self.assertRedirects(r, "/yeni/", fetch_redirect_response=False)

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_topbar_reflects_login_state_without_email(self):
        anon = self.client.get("/")
        self.assertContains(anon, "Giriş")
        self.client.force_login(self.user)
        r = self.client.get("/")
        self.assertContains(r, "@ali_k")
        self.assertContains(r, "Çıkış")
        self.assertNotContains(r, "ali@example.com")


class UserModelTests(TestCase):
    def test_db_constraint_blocks_case_variant_username(self):
        from django.db import IntegrityError, transaction

        User.objects.create_user(email="a@example.com", username="ali_k", password="x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([User(email="b@example.com", username="ALI_K", password="x")])
