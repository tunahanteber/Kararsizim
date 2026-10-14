from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render


def health(request):
    """Faz 1 sağlık kontrolü: DB'ye SELECT 1 atar."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"db": "ok"})


def csrf_failure(request, reason=""):
    """Ham Django 403 sayfası yerine Türkçe, çıkış yolu olan bir sayfa.

    Giriş/kayıt formu iki kez gönderilirse ikincisi eski token'la gelir; kullanıcı
    zaten giriş yapmışsa hata göstermeden ana sayfaya al.
    """
    if request.user.is_authenticated and request.path in ("/giris/", "/kayit/"):
        return redirect("/")
    return render(request, "403_csrf.html", status=403)
