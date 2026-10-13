from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import SignInView, SignUpView

urlpatterns = [
    path("kayit/", SignUpView.as_view(), name="signup"),
    path("giris/", SignInView.as_view(), name="login"),
    path("cikis/", LogoutView.as_view(), name="logout"),
]
