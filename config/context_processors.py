from django.conf import settings


def asset_version(request):
    """CSS/JS adreslerine `?v=<değişiklik zamanı>` eklemek için (tarayıcı önbelleği eski dosyayı tutmasın)."""
    latest = 0
    for rel in ("css/app.css", "js/app.js"):
        try:
            latest = max(latest, int((settings.BASE_DIR / "static" / rel).stat().st_mtime))
        except OSError:
            pass
    return {"ASSET_VERSION": latest}
