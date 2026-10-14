from django.contrib import admin
from django.db.models import Count
from django.utils import timezone

from .models import Option, Poll, Report, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "code", "created_at", "closed_at", "report_count")
    list_filter = ("closed_at",)
    search_fields = ("question", "code", "author__username")
    inlines = [OptionInline]
    actions = ["close_polls"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_reports=Count("reports"))

    @admin.display(description="Şikâyet", ordering="_reports")
    def report_count(self, obj):
        return obj._reports

    @admin.action(description="Seçili anketleri kapat")
    def close_polls(self, request, queryset):
        queryset.filter(closed_at__isnull=True).update(closed_at=timezone.now())


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("poll", "reason", "note", "created_at")
    list_filter = ("reason",)
    search_fields = ("poll__question", "note")
    raw_id_fields = ("poll",)


admin.site.register(Vote)
