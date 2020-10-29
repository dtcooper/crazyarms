from django.apps import apps, AppConfig

from django.db.models.signals import post_migrate


def create_user_perm_group(codename, description):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    from .models import User

    user = ContentType.objects.get_for_model(User)
    group, _ = Group.objects.get_or_create(name=description)
    group.permissions.add(Permission.objects.get_or_create(
        content_type=user, codename=codename, defaults={'name': description})[0])


def create_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    from broadcast.models import Broadcast, BroadcastAsset

    # Go in alphabetical order
    broadcast = ContentType.objects.get_for_model(Broadcast)
    broadcast_asset = ContentType.objects.get_for_model(BroadcastAsset)
    group, _ = Group.objects.get_or_create(name='Add prerecorded broadcasts')
    group.permissions.add(*Permission.objects.filter(content_type__in=(broadcast, broadcast_asset)))

    # TODO find a way to hide view_websockify in admin
    create_user_perm_group('view_websockify', 'Can configure and administrate Zoom over VNC')
    create_user_perm_group('view_logs', 'Can view server logs')
    create_user_perm_group('change_liquidsoap', 'Edit Liquidsoap harbor source code')

    constance = apps.get_app_config('constance')
    constance.create_perm()
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
