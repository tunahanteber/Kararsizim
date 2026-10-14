from django.contrib import admin
from django.urls import include, path

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("saglik/", health, name="health"),
    path("", include("polls.urls")),
]
