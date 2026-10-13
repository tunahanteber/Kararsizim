from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("saglik/", health, name="health"),
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
]
