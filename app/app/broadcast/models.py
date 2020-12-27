from django.db import models
from django.utils import timezone
from django.utils.formats import date_format

from huey.contrib.djhuey import revoke_by_id

from common.models import AudioAssetBase, TimestampedModel, after_db_commit


class BroadcastAsset(AudioAssetBase):
    UNNAMED_TRACK = "Unnamed Broadcast"
    UPLOAD_DIR = "broadcasts"

    class Meta:
        verbose_name = "scheduled broadcast asset"
        verbose_name_plural = "scheduled broadcast assets"
        ordering = ("title", "id")


class Broadcast(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "-", "to be queued"
        QUEUED = "q", "queued for play"
        PLAYED = "p", "played"
        FAILED = "f", "failed to play"

    asset = models.ForeignKey(
        BroadcastAsset,
        verbose_name="broadcast asset",
        related_name="broadcasts",
        on_delete=models.CASCADE,
    )
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.PENDING)
    task_id = models.UUIDField(null=True)

    def __init__(self, *args, **kwargs):
        self.queue_after_save = False
        super().__init__(*args, **kwargs)

    def __str__(self):
        scheduled_time = date_format(timezone.localtime(self.scheduled_time), "SHORT_DATETIME_FORMAT")
        return f"{self.asset} ({self.get_status_display()} at {scheduled_time})"

    class Meta:
        ordering = ("-scheduled_time",)
        verbose_name = "scheduled broadcast"
        verbose_name_plural = "scheduled broadcasts"

    @after_db_commit
    def queue(self):
        from .tasks import play_broadcast

        task = play_broadcast.schedule(args=(self,), eta=self.scheduled_time)
        Broadcast.objects.filter(id=self.id).update(task_id=task.id)

    def clean(self):
        if self.status == self.Status.PENDING:
            self.status = self.Status.QUEUED
            self.queue_after_save = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.queue_after_save:
            self.queue()

    def delete(self, *args, **kwargs):
        if self.task_id:
            revoke_by_id(self.task_id)
        return super().delete(*args, **kwargs)
