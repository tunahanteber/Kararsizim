from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import PollForm
from .models import Poll

User = get_user_model()

PAGE_SIZE = 20


def _poll_queryset():
    return (
        Poll.objects.select_related("author")
        .prefetch_related("options")
        .annotate(total_votes=Count("votes"))
    )


def _paginate(request, queryset):
    page = Paginator(queryset, PAGE_SIZE).get_page(request.GET.get("sayfa"))
    services.attach_feed_state(request, page.object_list)
    return page


def feed(request):
    popular = request.GET.get("sirala") == "populer"
    qs = _poll_queryset().order_by("-total_votes", "-created_at") if popular else _poll_queryset().order_by("-created_at")
    return render(request, "polls/feed.html", {"page": _paginate(request, qs), "popular": popular})


def profile(request, username):
    owner = get_object_or_404(User, username=username.lower())
    qs = _poll_queryset().filter(author=owner).order_by("-created_at")
    return render(request, "polls/profile.html", {"owner": owner, "page": _paginate(request, qs)})


def detail(request, code):
    poll = get_object_or_404(_poll_queryset(), code=code)
    vote = services.get_user_vote(request, poll)
    is_owner = request.user.is_authenticated and poll.author_id == request.user.id
    ctx = {
        "poll": poll,
        "options": list(poll.options.all()),
        "is_owner": is_owner,
        "voted_position": vote.option.position if vote else None,
        # Sonuçlar yalnızca görme hakkı olana hesaplanır; aksi halde şablona hiç girmez.
        "data": services.get_results(poll) if (vote or is_owner) else None,
    }
    return render(request, "polls/detail.html", ctx)


@login_required
def create(request):
    form = PollForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        poll = services.create_poll(
            author=request.user,
            question=form.cleaned_data["question"],
            details=form.cleaned_data["details"],
            indecision_level=form.cleaned_data["indecision_level"],
            option_texts=form.cleaned_data["option_texts"],
        )
        messages.success(request, "Anketin yayında! Şimdi paylaş, fikir topla.")
        return redirect("poll_detail", code=poll.code)
    return render(request, "polls/create.html", {"form": form})


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@require_POST
def vote(request, code):
    poll = get_object_or_404(Poll.objects.prefetch_related("options"), code=code)
    try:
        position = int(request.POST.get("option", ""))
    except ValueError:
        return _bad_vote(request)
    option = next((o for o in poll.options.all() if o.position == position), None)
    if option is None:
        return _bad_vote(request)

    cast, already = services.cast_vote(request, poll, option)

    if _wants_json(request):
        data = services.get_results(poll)
        return JsonResponse(
            {
                "ok": True,
                "already_voted": already,
                "voted_option": cast.option.position,
                "total": data["total"],
                "results": data["results"],
                "verdict": {"key": data["verdict"]["key"], "label": data["verdict"]["label"]},
            }
        )
    messages.info(request, "Zaten oy verdin, işte sonuçlar." if already else "Oyun kaydedildi!")
    return redirect("poll_detail", code=poll.code)


def _bad_vote(request):
    if _wants_json(request):
        return JsonResponse({"ok": False, "error": "Geçersiz seçenek."}, status=400)
    return HttpResponseBadRequest("Geçersiz seçenek.")


@require_POST
@login_required
def delete(request, code):
    poll = get_object_or_404(Poll, code=code)
    if poll.author_id != request.user.id:
        return HttpResponseForbidden("Bu anket senin değil.")
    poll.delete()
    messages.success(request, "Anket silindi.")
    return redirect("home")
