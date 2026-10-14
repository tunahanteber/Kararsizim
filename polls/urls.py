from django.urls import path, re_path

from . import views

CODE = r"(?P<code>[2-9a-hjkmnp-z]{12})"

urlpatterns = [
    path("", views.feed, name="home"),
    path("yeni/", views.create, name="poll_create"),
    re_path(rf"^a/{CODE}/$", views.detail, name="poll_detail"),
    re_path(rf"^a/{CODE}/oy/$", views.vote, name="poll_vote"),
    re_path(rf"^a/{CODE}/sil/$", views.delete, name="poll_delete"),
    path("u/<str:username>/", views.profile, name="profile"),
]
