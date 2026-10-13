from django.db import connection
from django.http import JsonResponse


def health(request):
    """Faz 1 sağlık kontrolü: DB'ye SELECT 1 atar."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"db": "ok"})
