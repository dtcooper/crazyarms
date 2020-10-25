from django.apps import apps, AppConfig

from django.db.models.signals import post_migrate


def create_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from broadcast.models import Broadcast, BroadcastAsset
    from .models import User

    constance = apps.get_app_config('constance')
    constance.create_perm()

    broadcast = ContentType.objects.get_for_model(Broadcast)
    broadcast_asset = ContentType.objects.get_for_model(BroadcastAsset)
    group, _ = Group.objects.get_or_create(name='Add prerecorded broadcasts')
    group.permissions.add(*Permission.objects.filter(content_type__in=(broadcast, broadcast_asset)))

    user = ContentType.objects.get_for_model(User)
    group, _ = Group.objects.get_or_create(name='Can view server logs')
    group.permissions.add(Permission.objects.get_or_create(
        content_type=user, codename='view_logs', defaults={'name': 'Can view server logs'})[0])

    user = ContentType.objects.get_for_model(User)
    group, _ = Group.objects.get_or_create(name='Can administer Zoom over VNC')
    group.permissions.add(Permission.objects.get_or_create(
        content_type=user, codename='view_websockify', defaults={'name': 'Can view server logs'})[0])

    group, _ = Group.objects.get_or_create(name='Modify settings and configuration')
    group.permissions.add(Permission.objects.get(codename='change_config'))


class CommonConfig(AppConfig):
    name = 'common'
    verbose_name = 'Authentication and Authorization'

    def ready(self):
        from constance.apps import ConstanceConfig
        from constance.admin import Config

        ConstanceConfig.verbose_name = 'Server Settings'
        Config._meta.verbose_name = 'Configuration'
        Config._meta.verbose_name_plural = 'Configuration'

        post_migrate.connect(create_groups, sender=self)
