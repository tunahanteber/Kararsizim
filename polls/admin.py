from django.contrib import admin

from .models import Option, Poll, Vote


class OptionInline(admin.TabularInline):
    model = Option
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("question", "author", "code", "created_at")
    search_fields = ("question", "code", "author__username")
    inlines = [OptionInline]


admin.site.register(Vote)
