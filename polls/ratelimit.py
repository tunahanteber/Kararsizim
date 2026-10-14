import hashlib
import time

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    # Vercel istemci IP'sini X-Forwarded-For'a yazar (ilk değer).
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def is_limited(request, scope: str) -> bool:
    """IP başına sabit pencereli sayaç (DB cache). Her çağrı bir istek sayılır.

    Ham IP cache anahtarına yazılmaz; SECRET_KEY ile hash'lenir. Sayaç basit
    tutulmuştur (get+set, atomik değil): amaç kaba kötüye kullanım sınırıdır.
    """
    limit, window = settings.RATE_LIMITS[scope]
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{client_ip(request)}".encode()).hexdigest()[:24]
    key = f"rl:{scope}:{digest}:{int(time.time() // window)}"
    count = cache.get(key, 0) + 1
    cache.set(key, count, timeout=window + 5)  # timeout açıkça verilir; varsayılan 300 sn saatlik sınırı bozardı
    return count > limit
