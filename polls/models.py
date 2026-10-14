from django.conf import settings
from django.db import models
from django.db.models import Q

LEVELS = {
    1: "Biraz kararsız",
    2: "Çok kararsız",
    3: "Tam bir kararsız",
}


class Poll(models.Model):
    # `id` yalnızca dahilidir; URL'de ve HTML'de asla görünmez (kod kullanılır).
    code = models.CharField(max_length=12, unique=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls"
    )
    question = models.CharField(max_length=160)
    details = models.CharField(max_length=300, blank=True)
    indecision_level = models.PositiveSmallIntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)  # doluysa anket kapalı: yeni oy alınmaz

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(indecision_level__in=[1, 2, 3]), name="poll_level_1_to_3"
            ),
        ]

    def __str__(self):
        return self.question

    @property
    def is_closed(self):
        return self.closed_at is not None

    @property
    def level_label(self):
        return LEVELS[self.indecision_level]


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=80)
    position = models.PositiveSmallIntegerField()  # 0-4; renk buna göre atanır

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["poll", "position"], name="uniq_option_position"),
            models.CheckConstraint(condition=Q(position__lte=4), name="option_position_0_to_4"),
        ]

    def __str__(self):
        return self.text


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE
    )
    voter_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "user"],
                condition=Q(user__isnull=False),
                name="uniq_vote_per_user",
            ),
            models.UniqueConstraint(
                fields=["poll", "voter_hash"],
                condition=Q(voter_hash__isnull=False),
                name="uniq_vote_per_anon",
            ),
            models.CheckConstraint(
                condition=(
                    Q(user__isnull=False, voter_hash__isnull=True)
                    | Q(user__isnull=True, voter_hash__isnull=False)
                ),
                name="vote_exactly_one_identity",
            ),
        ]


class Report(models.Model):
    """Şikâyet: yalnızca Django admin'de görülür; herkese açık hiçbir yerde gösterilmez."""

    REASONS = [
        ("spam", "Spam / reklam"),
        ("uygunsuz", "Uygunsuz içerik"),
        ("taciz", "Hakaret / taciz"),
        ("diger", "Diğer"),
    ]

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=12, choices=REASONS)
    note = models.CharField(max_length=200, blank=True)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="+"
    )
    reporter_hash = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "reporter"], condition=Q(reporter__isnull=False), name="uniq_report_per_user"
            ),
            models.UniqueConstraint(
                fields=["poll", "reporter_hash"], condition=Q(reporter_hash__isnull=False), name="uniq_report_per_anon"
            ),
            models.CheckConstraint(
                condition=(
                    Q(reporter__isnull=False, reporter_hash__isnull=True)
                    | Q(reporter__isnull=True, reporter_hash__isnull=False)
                ),
                name="report_exactly_one_identity",
            ),
        ]

    def __str__(self):
        return f"{self.get_reason_display()} · {self.poll}"
