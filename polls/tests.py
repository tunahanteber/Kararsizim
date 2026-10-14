import re

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from . import services
from .models import Option, Poll, Vote

User = get_user_model()
PASSWORD = "Sagl4m-Parola!"


def make_user(name="ali_k", email=None):
    return User.objects.create_user(email=email or f"{name}@example.com", username=name, password=PASSWORD)


def make_poll(author, options=("Sinema", "Restoran"), question="Bu akşam ne yapsam?", level=2):
    return services.create_poll(author, question, "", level, list(options))


class CodeTests(TestCase):
    def test_generate_poll_code(self):
        for _ in range(200):
            code = services.generate_poll_code()
            self.assertEqual(len(code), 12)
            self.assertTrue(set(code) <= set(services.CODE_ALPHABET))


class PercentTests(TestCase):
    def test_largest_remainder_sums_to_100(self):
        for counts in ([1, 1, 1], [1, 1, 1, 1, 1, 1][:5], [7, 3], [1, 2], [33, 33, 34], [5, 0], [2, 1, 1, 1, 1]):
            self.assertEqual(sum(services.largest_remainder(counts)), 100, counts)
        self.assertEqual(services.largest_remainder([1, 1, 1]), [34, 33, 33])
        self.assertEqual(services.largest_remainder([0, 0]), [0, 0])

    def verdict(self, counts):
        percents = services.largest_remainder(counts)
        results = [{"count": c, "percent": p} for c, p in zip(counts, percents)]
        return services.compute_verdict(results)["key"]

    def test_verdict_boundaries(self):
        self.assertEqual(self.verdict([1, 1]), "az_oy")           # toplam < 3
        self.assertEqual(self.verdict([11, 10]), "kil_payi")      # fark ~5 puan altı
        self.assertEqual(self.verdict([51, 49]), "kil_payi")      # fark 2
        self.assertEqual(self.verdict([105, 95]), "basa_bas")     # 52.5/47.5 yuvarlanınca 53/47 → fark 6
        self.assertEqual(self.verdict([55, 45]), "basa_bas")      # fark 10
        self.assertEqual(self.verdict([57, 43]), "basa_bas")      # fark 14 (iki seçenekte fark hep çift)
        self.assertEqual(self.verdict([58, 42]), "one_cikan")     # fark 16
        self.assertEqual(self.verdict([60, 40]), "one_cikan")     # fark 20, lider < 70
        self.assertEqual(self.verdict([70, 30]), "net_karar")     # lider 70
        self.assertEqual(self.verdict([100, 0]), "net_karar")


class CreatePollTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def post(self, **overrides):
        data = {"question": "Sinema mı restoran mı?", "details": "", "indecision_level": "2",
                "option_0": "Sinema", "option_1": "Restoran"}
        data.update(overrides)
        return self.client.post(reverse("poll_create"), data)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse("poll_create"))
        self.assertRedirects(r, "/giris/?next=/yeni/", fetch_redirect_response=False)

    def test_create_success(self):
        self.client.force_login(self.user)
        r = self.post()
        poll = Poll.objects.get()
        self.assertRedirects(r, f"/a/{poll.code}/", fetch_redirect_response=False)
        self.assertEqual([o.text for o in poll.options.all()], ["Sinema", "Restoran"])

    def test_one_option_rejected(self):
        self.client.force_login(self.user)
        r = self.post(option_1="")
        self.assertContains(r, "En az 2 seçenek")
        self.assertEqual(Poll.objects.count(), 0)

    def test_six_options_rejected_by_service(self):
        with self.assertRaises(ValueError):
            services.create_poll(self.user, "Altı seçenek?", "", 2, list("abcdef"))

    def test_five_options_ok_and_gaps_ignored(self):
        self.client.force_login(self.user)
        self.post(option_2="Kafe", option_3="", option_4="Park")
        self.assertEqual([o.text for o in Poll.objects.get().options.all()], ["Sinema", "Restoran", "Kafe", "Park"])

    def test_duplicate_options_rejected(self):
        self.client.force_login(self.user)
        r = self.post(option_1=" sinema ")
        self.assertContains(r, "Aynı seçeneği")
        self.assertEqual(Poll.objects.count(), 0)

    def test_short_question_rejected(self):
        self.client.force_login(self.user)
        r = self.post(question="abc")
        self.assertContains(r, "en az 5 karakter")


class VoteTests(TestCase):
    def setUp(self):
        self.author = make_user("yazar")
        self.poll = make_poll(self.author)

    def vote(self, position, client=None, json=True, poll=None):
        poll = poll or self.poll
        headers = {"HTTP_ACCEPT": "application/json"} if json else {}
        return (client or self.client).post(reverse("poll_vote", args=[poll.code]), {"option": position}, **headers)

    def test_anonymous_vote_then_duplicate(self):
        r = self.vote(0)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["already_voted"])
        self.assertEqual(body["total"], 1)
        r2 = self.vote(1)
        self.assertTrue(r2.json()["already_voted"])
        self.assertEqual(r2.json()["voted_option"], 0)
        self.assertEqual(Vote.objects.count(), 1)

    def test_anonymous_vote_stores_hash_not_session_key(self):
        self.vote(0)
        v = Vote.objects.get()
        self.assertIsNone(v.user)
        self.assertEqual(len(v.voter_hash), 64)
        self.assertNotEqual(v.voter_hash, self.client.session.session_key)

    def test_two_browsers_two_votes(self):
        self.vote(0)
        from django.test import Client
        self.vote(1, client=Client())
        self.assertEqual(Vote.objects.count(), 2)

    def test_member_vote_then_duplicate(self):
        voter = make_user("oyuncu")
        self.client.force_login(voter)
        self.assertFalse(self.vote(0).json()["already_voted"])
        self.assertTrue(self.vote(1).json()["already_voted"])
        self.assertEqual(Vote.objects.filter(user=voter).count(), 1)

    def test_invalid_option_returns_400(self):
        self.assertEqual(self.vote(4).status_code, 400)
        self.assertEqual(self.vote("x").status_code, 400)
        self.assertEqual(Vote.objects.count(), 0)

    def test_option_of_other_poll_rejected_by_service(self):
        other = make_poll(self.author, ("A", "B"), "Başka bir anket?")
        foreign = other.options.first()
        request = self.client.get("/").wsgi_request
        with self.assertRaises(ValueError):
            services.cast_vote(request, self.poll, foreign)

    def test_unknown_poll_404(self):
        r = self.client.post("/a/222222222222/oy/", {"option": 0})
        self.assertEqual(r.status_code, 404)

    def test_form_vote_redirects_to_detail(self):
        r = self.vote(0, json=False)
        self.assertRedirects(r, f"/a/{self.poll.code}/", fetch_redirect_response=False)

    def test_db_constraints(self):
        opt = self.poll.options.first()
        Vote.objects.create(poll=self.poll, option=opt, voter_hash="h" * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=opt, voter_hash="h" * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=opt)  # kimlik yok
        with self.assertRaises(IntegrityError), transaction.atomic():
            Vote.objects.create(poll=self.poll, option=opt, user=self.author, voter_hash="x")  # ikisi birden


class ResultPrivacyTests(TestCase):
    def setUp(self):
        self.author = make_user("yazar", "gizli.yazar@example.com")
        self.poll = make_poll(self.author)
        from django.test import Client
        for i in range(4):  # 3 Sinema, 1 Restoran
            Client().post(reverse("poll_vote", args=[self.poll.code]), {"option": 0 if i < 3 else 1})

    def test_unvoted_visitor_sees_no_distribution(self):
        html = self.client.get(reverse("poll_detail", args=[self.poll.code])).content.decode()
        self.assertIn("4 kişi oyladı", html)
        self.assertNotIn("%75", html)
        self.assertNotIn("%25", html)
        self.assertNotIn("3 oy", html)
        self.assertNotIn("result-row", html)
        self.assertIn("Sonuçlar oy verince görünür", html)

    def test_unvoted_json_not_available_without_voting(self):
        # Oy endpoint'i dışında dağılım veren bir JSON yok; detay HTML'i de yüzde içermiyor
        html = self.client.get("/").content.decode()
        self.assertNotRegex(html, r"%\d+")

    def test_after_vote_results_visible(self):
        self.client.post(reverse("poll_vote", args=[self.poll.code]), {"option": 0})
        html = self.client.get(reverse("poll_detail", args=[self.poll.code])).content.decode()
        self.assertIn("%80", html)  # 4 / 5 → 80
        self.assertIn("result-row", html)

    def test_author_always_sees_results(self):
        self.client.force_login(self.author)
        html = self.client.get(reverse("poll_detail", args=[self.poll.code])).content.decode()
        self.assertIn("%75", html)

    def test_feed_hides_results_until_voted(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("%75", html)
        self.client.post(reverse("poll_vote", args=[self.poll.code]), {"option": 1})
        html = self.client.get("/").content.decode()
        self.assertIn("aria-label=\"Sinema %", html)


class EmailLeakTests(TestCase):
    def test_author_email_never_rendered(self):
        author = make_user("yazar", "gizli.yazar@example.com")
        poll = make_poll(author)
        for url in ("/", f"/a/{poll.code}/", "/u/yazar/", "/u/YAZAR/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertNotContains(r, "gizli.yazar@example.com")
            self.assertNotContains(r, "gizli.yazar")
        self.client.force_login(author)
        for url in ("/", f"/a/{poll.code}/", "/u/yazar/"):
            self.assertNotContains(self.client.get(url), "gizli.yazar@example.com")

    def test_internal_id_not_exposed(self):
        author = make_user()
        poll = make_poll(author)
        html = self.client.get(f"/a/{poll.code}/").content.decode()
        self.assertIn(f"/a/{poll.code}/", html)
        self.assertNotIn(f"/a/{poll.pk}/", html)
        self.assertNotIn("poll_id", html)


class DeleteTests(TestCase):
    def setUp(self):
        self.author = make_user("yazar")
        self.poll = make_poll(self.author)

    def test_owner_can_delete_via_post(self):
        self.client.force_login(self.author)
        self.assertEqual(self.client.get(reverse("poll_delete", args=[self.poll.code])).status_code, 405)
        r = self.client.post(reverse("poll_delete", args=[self.poll.code]))
        self.assertRedirects(r, "/", fetch_redirect_response=False)
        self.assertEqual(Poll.objects.count(), 0)

    def test_other_user_cannot_delete(self):
        self.client.force_login(make_user("baskasi"))
        self.assertEqual(self.client.post(reverse("poll_delete", args=[self.poll.code])).status_code, 403)
        self.assertEqual(Poll.objects.count(), 1)

    def test_anonymous_redirected(self):
        r = self.client.post(reverse("poll_delete", args=[self.poll.code]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Poll.objects.count(), 1)


class FeedTests(TestCase):
    def test_pagination_and_sort_and_query_count(self):
        author = make_user("yazar")
        polls = [make_poll(author, question=f"Soru numara {i}?") for i in range(25)]
        from django.test import Client
        for _ in range(3):
            Client().post(reverse("poll_vote", args=[polls[0].code]), {"option": 0})
        r = self.client.get("/")
        self.assertEqual(len(r.context["page"].object_list), 20)
        self.assertEqual(len(self.client.get("/?sayfa=2").context["page"].object_list), 5)
        popular = self.client.get("/?sirala=populer").context["page"].object_list
        self.assertEqual(popular[0].code, polls[0].code)

    def test_no_n_plus_one(self):
        author = make_user("yazar")
        for i in range(3):
            make_poll(author, question=f"Soru numara {i}?")
        with self.assertNumQueries(3):  # sayım + anketler(+yazar) + seçenekler
            self.client.get("/")
        for i in range(10):
            make_poll(author, question=f"Ek soru numara {i}?")
        with self.assertNumQueries(3):
            self.client.get("/")

    def test_empty_state(self):
        self.assertContains(self.client.get("/"), "İlk sen ol")

    def test_profile_unknown_user_404(self):
        self.assertEqual(self.client.get("/u/yokboyle/").status_code, 404)


class SeedDemoTests(TestCase):
    def test_seed_is_idempotent_and_hides_nothing_sensitive(self):
        from django.core.management import call_command

        call_command("seed_demo", verbosity=0)
        count = Poll.objects.count()
        self.assertGreaterEqual(count, 6)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Poll.objects.count(), count)
        self.assertFalse(User.objects.get(username="elif_k").has_usable_password())
        html = self.client.get("/").content.decode()
        self.assertNotIn("demo.invalid", html)
        call_command("seed_demo", "--reset", verbosity=0)
        self.assertEqual(Poll.objects.count(), count)


class Faz4Tests(TestCase):
    def setUp(self):
        self.author = make_user("yazar")

    def test_leader_in_results(self):
        poll = make_poll(self.author, ("A", "B", "C"))
        from django.test import Client
        for pos in (1, 1, 2):
            Client().post(reverse("poll_vote", args=[poll.code]), {"option": pos})
        data = services.get_results(poll)
        self.assertEqual(data["leader"], 1)
        self.assertIsNone(services.get_results(make_poll(self.author, ("X", "Y"), "Oy yok sorusu?"))["leader"])

    def test_json_vote_response_shape_unchanged(self):
        poll = make_poll(self.author)
        r = self.client.post(reverse("poll_vote", args=[poll.code]), {"option": 0}, HTTP_ACCEPT="application/json")
        self.assertEqual(set(r.json()), {"ok", "already_voted", "voted_option", "total", "results", "verdict"})
        self.assertEqual(set(r.json()["verdict"]), {"key", "label"})

    def test_level_3_badge_spins_and_labels(self):
        poll3 = make_poll(self.author, level=3, question="Tam kararsız soru?")
        poll1 = make_poll(self.author, level=1, question="Biraz kararsız soru?")
        html = self.client.get("/").content.decode()
        self.assertIn("Tam bir kararsız", html)
        self.assertIn("Biraz kararsız", html)
        self.assertEqual(html.count("emoji spin"), 1)  # yalnızca seviye 3 döner

    def test_locked_bar_has_aria_and_no_percent(self):
        poll = make_poll(self.author)
        from django.test import Client
        Client().post(reverse("poll_vote", args=[poll.code]), {"option": 0})
        html = self.client.get(f"/a/{poll.code}/").content.decode()
        self.assertIn('aria-label="Sonuçlar oy verince görünür"', html)
        self.assertNotIn("is-leader", html)

    def test_voted_page_marks_leader_and_check(self):
        poll = make_poll(self.author)
        self.client.post(reverse("poll_vote", args=[poll.code]), {"option": 0})
        html = self.client.get(f"/a/{poll.code}/").content.decode()
        self.assertIn("is-leader", html)
        self.assertIn("seg-check", html)
        self.assertNotIn("data-vote-form", html)  # oy veren için form yok

    def test_custom_404_and_500_pages(self):
        from django.test import override_settings
        with override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"]):
            r = self.client.get("/yok/boyle/bir/sayfa/")
            self.assertContains(r, "kararsız kalmış", status_code=404)
        from django.template.loader import render_to_string
        self.assertIn("Biz de şaşırdık", render_to_string("500.html"))

    def test_page_has_favicon_skip_link_and_asset_version(self):
        html = self.client.get("/").content.decode()
        self.assertIn("favicon.svg", html)
        self.assertIn('href="#icerik"', html)
        self.assertRegex(html, r"app\.css\?v=\d+")
