import hashlib
import hmac
import re
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from .models import Option, Poll, Report, Vote

CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
CODE_LENGTH = 12
MIN_OPTIONS, MAX_OPTIONS = 2, 5

VERDICTS = {
    "kil_payi": "Kıl payı",
    "basa_bas": "Başa baş",
    "net_karar": "Net karar",
    "one_cikan": "Öne çıkan var",
    "az_oy": "Henüz erken",
}


def generate_poll_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def normalize_option_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def create_poll(author, question, details, indecision_level, option_texts) -> Poll:
    texts = [normalize_option_text(t) for t in option_texts if normalize_option_text(t)]
    if not MIN_OPTIONS <= len(texts) <= MAX_OPTIONS:
        raise ValueError("Seçenek sayısı 2 ile 5 arasında olmalı.")
    if len({t.casefold() for t in texts}) != len(texts):
        raise ValueError("Seçenekler birbirinden farklı olmalı.")

    for _ in range(5):
        try:
            with transaction.atomic():
                poll = Poll.objects.create(
                    code=generate_poll_code(),
                    author=author,
                    question=question.strip(),
                    details=(details or "").strip(),
                    indecision_level=indecision_level,
                )
                Option.objects.bulk_create(
                    [Option(poll=poll, text=t, position=i) for i, t in enumerate(texts)]
                )
            return poll
        except IntegrityError:
            continue  # kod çakışması: yeni kodla tekrar dene
    raise RuntimeError("Anket kodu üretilemedi.")


def anon_voter_hash(request) -> str:
    if not request.session.session_key:
        request.session.save()
    key = request.session.session_key.encode()
    return hmac.new(settings.SECRET_KEY.encode(), key, hashlib.sha256).hexdigest()


def _existing_anon_hash(request):
    """Oturum yoksa oluşturmadan hash üretir (GET isteklerinde oturum açmamak için)."""
    if not request.session.session_key:
        return None
    return anon_voter_hash(request)


def _identity_filter(request):
    if request.user.is_authenticated:
        return {"user": request.user}
    voter_hash = _existing_anon_hash(request)
    return {"voter_hash": voter_hash} if voter_hash else None


def get_user_vote(request, poll):
    flt = _identity_filter(request)
    if flt is None:
        return None
    return Vote.objects.filter(poll=poll, **flt).select_related("option").first()


class PollClosed(Exception):
    """Kapalı ankete oy verilmeye çalışıldı."""


def close_poll(poll):
    if poll.closed_at is None:
        poll.closed_at = timezone.now()
        poll.save(update_fields=["closed_at"])


def cast_vote(request, poll, option):
    """Oy kaydeder. (vote, already_voted) döner."""
    if option.poll_id != poll.id:
        raise ValueError("Seçenek bu ankete ait değil.")
    if poll.is_closed:
        raise PollClosed

    if request.user.is_authenticated:
        identity = {"user": request.user}
    else:
        identity = {"voter_hash": anon_voter_hash(request)}

    try:
        with transaction.atomic():
            vote = Vote.objects.create(poll=poll, option=option, **identity)
        return vote, False
    except IntegrityError:
        existing = Vote.objects.filter(poll=poll, **identity).select_related("option").first()
        return existing, True


def can_see_results(request, poll) -> bool:
    # Kapalı ankette yeni oy gelmeyeceği için sürü etkisi kalmaz: sonuçlar herkese açık.
    if poll.is_closed:
        return True
    if request.user.is_authenticated and poll.author_id == request.user.id:
        return True
    return get_user_vote(request, poll) is not None


def largest_remainder(counts):
    """Yüzdeleri tam sayıya yuvarlar; toplam (oy varsa) 100 olur."""
    total = sum(counts)
    if total == 0:
        return [0] * len(counts)
    exact = [c * 100 / total for c in counts]
    floors = [int(e) for e in exact]
    remaining = 100 - sum(floors)
    order = sorted(range(len(counts)), key=lambda i: (-(exact[i] - floors[i]), i))
    for i in order[:remaining]:
        floors[i] += 1
    return floors


def compute_verdict(results):
    total = sum(r["count"] for r in results)
    key = "one_cikan"
    if total < 3:
        key = "az_oy"
    else:
        percents = sorted((r["percent"] for r in results), reverse=True)
        lead, second = percents[0], percents[1] if len(percents) > 1 else 0
        if lead - second <= 5:
            key = "kil_payi"
        elif lead - second <= 15:
            key = "basa_bas"
        elif lead >= 70:
            key = "net_karar"
    return {"key": key, "label": VERDICTS[key]}


def build_results(options, counts_by_option):
    options = sorted(options, key=lambda o: o.position)
    counts = [counts_by_option.get(o.id, 0) for o in options]
    percents = largest_remainder(counts)
    results = [
        {"position": o.position, "text": o.text, "count": c, "percent": p}
        for o, c, p in zip(options, counts, percents)
    ]
    total = sum(counts)
    leader = max(results, key=lambda r: r["count"])["position"] if total else None
    return {"total": total, "results": results, "verdict": compute_verdict(results), "leader": leader}


def get_results(poll):
    counts = dict(
        Vote.objects.filter(poll=poll).values_list("option_id").annotate(c=Count("id"))
    )
    return build_results(poll.options.all(), counts)


def attach_feed_state(request, polls):
    """Akış/profil kartları için: her ankete `voted_position` ve (görebiliyorsa) `results` ekler.

    Sabit sayıda sorgu çalıştırır (N+1 yok). Sonuçlar yalnızca görme hakkı olan
    anketlere eklenir; diğerleri için `results` None'dır.
    """
    polls = list(polls)
    if not polls:
        return polls
    ids = [p.id for p in polls]

    voted = {}
    flt = _identity_filter(request)
    if flt is not None:
        rows = Vote.objects.filter(poll_id__in=ids, **flt).values_list("poll_id", "option__position")
        voted = dict(rows)

    user_id = request.user.id if request.user.is_authenticated else None
    visible = [p for p in polls if p.id in voted or p.author_id == user_id or p.is_closed]
    counts = {}
    if visible:
        for poll_id, option_id, c in (
            Vote.objects.filter(poll_id__in=[p.id for p in visible])
            .values_list("poll_id", "option_id")
            .annotate(c=Count("id"))
        ):
            counts.setdefault(poll_id, {})[option_id] = c

    for p in polls:
        p.voted_position = voted.get(p.id)
        p.results = (
            build_results(p.options.all(), counts.get(p.id, {})) if p in visible else None
        )
    return polls


def exclude_voted(request, queryset):
    """Akış filtresi: kullanıcının (veya bu oturumun) henüz oy vermediği, açık anketler."""
    queryset = queryset.filter(closed_at__isnull=True)
    flt = _identity_filter(request)
    if flt is None:
        return queryset
    return queryset.exclude(pk__in=Vote.objects.filter(**flt).values("poll_id"))


def report_poll(request, poll, reason, note=""):
    """Şikâyet kaydeder. (report, already_reported) döner."""
    if request.user.is_authenticated:
        identity = {"reporter": request.user}
    else:
        identity = {"reporter_hash": anon_voter_hash(request)}
    try:
        with transaction.atomic():
            return Report.objects.create(poll=poll, reason=reason, note=note.strip()[:200], **identity), False
    except IntegrityError:
        return Report.objects.filter(poll=poll, **identity).first(), True
