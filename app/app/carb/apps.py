from django.apps import apps, AppConfig
from django.db.models.signals import post_migrate


def create_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from .models import PrerecordedBroadcast

    constance = apps.get_app_config('constance')
    constance.create_perm()

    prerecorded_broadcast = ContentType.objects.get_for_model(PrerecordedBroadcast)
    group, _ = Group.objects.get_or_create(name='Create and delete prerecorded broadcasts')
    group.permissions.add(*Permission.objects.filter(content_type=prerecorded_broadcast))

    group, _ = Group.objects.get_or_create(name='Modify settings and configuration')
    group.permissions.add(Permission.objects.get(codename='change_config'))


class CarbConfig(AppConfig):
    name = 'carb'
    verbose_name = 'Crazy Arms Radio Backend'

    def ready(self):
        from constance.apps import ConstanceConfig
        from constance.admin import Config

        ConstanceConfig.verbose_name = 'Settings'
        Config._meta.verbose_name = 'Configuration'
        Config._meta.verbose_name_plural = 'Configuration'

        post_migrate.connect(create_groups, sender=self)
