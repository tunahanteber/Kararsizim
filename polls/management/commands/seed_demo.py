import hashlib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from polls.models import Option, Poll, Vote
from polls.services import create_poll

User = get_user_model()

DEMO_USERS = ["elif_k", "mert.d", "zeynep", "can_t"]

# (yazar, soru, açıklama, seviye, [(seçenek, oy sayısı)], kaç dakika önce)
DEMO_POLLS = [
    ("elif_k", "Bu akşam sinemaya mı gitsem, restorana mı?", "Hem film hem yemek canım çekiyor ama ikisine de yetişemem.", 2,
     [("Sinema", 14), ("Restoran", 12)], 7),
    ("mert.d", "Yeni telefon: iPhone mu Android mi?", "Bütçem 30 bin TL civarı.", 3,
     [("iPhone", 18), ("Android", 22), ("Eski telefonla devam", 5)], 45),
    ("zeynep", "Hafta sonu nereye kaçsam?", "Cuma akşamı çıkıp pazar dönmeyi düşünüyorum.", 2,
     [("Kapadokya", 12), ("Ege'de bir koy", 19), ("Karadeniz yaylaları", 9), ("İstanbul'da kal", 4), ("Bozcaada", 7)], 130),
    ("can_t", "Kahve mi çay mı?", "", 1, [("Kahve", 9), ("Çay", 31)], 260),
    ("elif_k", "Saçımı kısa mı kestirsem?", "Omuz hizasından bob'a geçmek üzereyim.", 3,
     [("Kısa kestir!", 21), ("Böyle kalsın", 17)], 400),
    ("mert.d", "Sabah mı akşam mı spor yapmalı?", "", 1, [("Sabah", 20), ("Akşam", 19)], 720),
    ("zeynep", "Pizza mı hamburger mi lahmacun mu?", "Sadece birini seçebilirsin.", 1,
     [("Pizza", 11), ("Hamburger", 8), ("Lahmacun", 27)], 1500),
    ("can_t", "Yeni işe geçmeli miyim?", "Maaş %30 fazla ama yol 1 saat uzuyor.", 3,
     [("Evet, geç", 2), ("Hayır, kal", 0)], 3),
]


class Command(BaseCommand):
    help = "Test için örnek kullanıcılar, anketler ve oylar oluşturur (tekrar çalıştırılabilir)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Önce örnek verileri sil.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            deleted, _ = User.objects.filter(username__in=DEMO_USERS).delete()
            self.stdout.write(f"{deleted} kayıt silindi.")

        users = {}
        for name in DEMO_USERS:
            user, created = User.objects.get_or_create(
                username=name, defaults={"email": f"{name.replace('.', '_')}@demo.invalid"}
            )
            if created:
                user.set_unusable_password()  # örnek hesaplarla giriş yapılamaz
                user.save()
            users[name] = user

        now = timezone.now()
        made = 0
        for author, question, details, level, options, minutes_ago in DEMO_POLLS:
            if Poll.objects.filter(author=users[author], question=question).exists():
                continue
            poll = create_poll(users[author], question, details, level, [o[0] for o in options])
            opts_by_pos = {o.position: o for o in Option.objects.filter(poll=poll)}
            votes = []
            for pos, (_, count) in enumerate(options):
                for i in range(count):
                    seed = f"demo:{poll.code}:{pos}:{i}".encode()
                    votes.append(Vote(poll=poll, option=opts_by_pos[pos], voter_hash=hashlib.sha256(seed).hexdigest()))
            Vote.objects.bulk_create(votes)
            Poll.objects.filter(pk=poll.pk).update(created_at=now - timedelta(minutes=minutes_ago))
            made += 1
        self.stdout.write(self.style.SUCCESS(f"{made} örnek anket oluşturuldu."))
