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


def create_perm_group_for_models(models, description):
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType

    if not isinstance(models, (tuple, list)):
        models = (models,)

    content_types = [ContentType.objects.get_for_model(model) for model in models]
    group, _ = Group.objects.get_or_create(name=description)
    group.permissions.add(*Permission.objects.filter(content_type__in=content_types))


def create_groups(sender, **kwargs):
    from django.contrib.auth.models import Group, Permission

    from broadcast.models import Broadcast, BroadcastAsset
    from autodj.models import AudioAsset, Playlist
    from services.models import PlayoutLogEntry

    create_perm_group_for_models((Broadcast, BroadcastAsset), 'Add prerecorded broadcasts')
    create_perm_group_for_models(PlayoutLogEntry, 'Advanced view of the playout log in admin site')
    create_perm_group_for_models((AudioAsset, Playlist), 'Program the AutoDJ')

    create_user_perm_group('view_telnet', 'Access Liquidsoap harbor over telnet (experimental)')
    create_user_perm_group('view_websockify', 'Can configure and administrate Zoom over VNC')
    create_user_perm_group('view_logs', 'Can view server logs')
    create_user_perm_group('change_liquidsoap', 'Edit Liquidsoap harbor source code')
    create_user_perm_group('can_boot', 'Can kick DJs off of harbor')

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
