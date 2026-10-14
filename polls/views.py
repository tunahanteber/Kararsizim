from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import ratelimit, services
from .forms import PollForm, ReportForm
from .models import Poll, Report

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
    unvoted = request.GET.get("filtre") == "oy-vermediklerim"
    qs = _poll_queryset()
    if unvoted:
        qs = services.exclude_voted(request, qs)
    qs = qs.order_by("-total_votes", "-created_at") if popular else qs.order_by("-created_at")
    base_qs = "sirala=populer&" if popular else ("filtre=oy-vermediklerim&" if unvoted else "")
    return render(
        request,
        "polls/feed.html",
        {"page": _paginate(request, qs), "popular": popular, "unvoted": unvoted, "base_qs": base_qs},
    )


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
        "report_form": ReportForm(),
        "voted_position": vote.option.position if vote else None,
        # Sonuçlar yalnızca görme hakkı olana hesaplanır; aksi halde şablona hiç girmez.
        "data": services.get_results(poll) if (vote or is_owner or poll.is_closed) else None,
    }
    return render(request, "polls/detail.html", ctx)


@login_required
def create(request):
    form = PollForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if ratelimit.is_limited(request, "poll"):
            form.add_error(None, "Bu saat için çok fazla anket açtın. Biraz sonra tekrar dene.")
            return render(request, "polls/create.html", {"form": form}, status=429)
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
    if ratelimit.is_limited(request, "vote"):
        return _too_fast(request)
    poll = get_object_or_404(Poll.objects.prefetch_related("options"), code=code)
    try:
        position = int(request.POST.get("option", ""))
    except ValueError:
        return _bad_vote(request)
    option = next((o for o in poll.options.all() if o.position == position), None)
    if option is None:
        return _bad_vote(request)

    try:
        cast, already = services.cast_vote(request, poll, option)
    except services.PollClosed:
        if _wants_json(request):
            return JsonResponse({"ok": False, "error": "Bu anket kapandı."}, status=409)
        messages.info(request, "Bu anket kapandı, artık oy verilemiyor.")
        return redirect("poll_detail", code=poll.code)

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


def _too_fast(request):
    text = "Çok hızlı gidiyorsun, biraz bekle ve tekrar dene."
    if _wants_json(request):
        return JsonResponse({"ok": False, "error": text}, status=429)
    return render(request, "429.html", status=429)


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


@require_POST
@login_required
def close(request, code):
    poll = get_object_or_404(Poll, code=code)
    if poll.author_id != request.user.id:
        return HttpResponseForbidden("Bu anket senin değil.")
    services.close_poll(poll)
    messages.success(request, "Anket kapandı. Artık yeni oy almıyor, sonuçlar herkese açık.")
    return redirect("poll_detail", code=poll.code)


@require_POST
def report(request, code):
    if ratelimit.is_limited(request, "report"):
        messages.error(request, "Çok fazla şikâyet gönderdin, biraz sonra tekrar dene.")
        return redirect("poll_detail", code=code)
    poll = get_object_or_404(Poll, code=code)
    if request.user.is_authenticated and poll.author_id == request.user.id:
        return HttpResponseForbidden("Kendi anketini şikâyet edemezsin.")
    form = ReportForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Şikâyet nedenini seçmelisin.")
        return redirect("poll_detail", code=poll.code)
    _, already = services.report_poll(request, poll, form.cleaned_data["reason"], form.cleaned_data["note"])
    messages.info(request, "Bu anketi zaten şikâyet etmiştin." if already else "Şikâyetin bize ulaştı, teşekkürler.")
    return redirect("poll_detail", code=poll.code)
