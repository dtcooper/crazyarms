from django.db import models
from django.utils import timezone

from huey.contrib.djhuey import revoke_by_id


from common.models import after_db_commit, AudioAssetBase, TimestampedModel


class BroadcastAsset(AudioAssetBase):
    class Meta:
        verbose_name = 'scheduled broadcast asset'
        verbose_name_plural = 'scheduled broadcast assets'


class Broadcast(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = '-', 'pending'
        QUEUED = 'q', 'queued'
        PLAYED = 'p', 'played'
        FAILED = 'f', 'queuing failed'

    asset = models.ForeignKey(BroadcastAsset, verbose_name='audio file', on_delete=models.CASCADE)
    scheduled_time = models.DateTimeField()
    status = models.CharField(max_length=1, choices=Status.choices, default=Status.PENDING)
    task_id = models.UUIDField(null=True)

    def __str__(self):
        return f'{self.asset} @ {timezone.localtime(self.scheduled_time)} [{self.get_status_display()}]'

    class Meta:
        ordering = ('-scheduled_time',)
        verbose_name = 'scheduled broadcast'
        verbose_name_plural = 'scheduled broadcasts'

    @after_db_commit
    def queue(self):
        from .tasks import play_prerecorded_broadcast

        task = play_prerecorded_broadcast.schedule(args=(self,), eta=self.scheduled_time)
        Broadcast.objects.filter(id=self.id).update(task_id=task.id)
        # Only update the status to queued if it's still PENDING -- so we don't thrash with
        # task if it's already updated the status
        Broadcast.objects.filter(id=self.id, status=Broadcast.Status.PENDING).update(
            status=Broadcast.Status.QUEUED)

    def delete(self, *args, **kwargs):
        if self.task_id:
            revoke_by_id(self.task_id)
        return super().delete(*args, **kwargs)
