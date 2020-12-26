from functools import wraps
import secrets

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group
from django.core import signing
from django.core.cache import cache
from django.urls import reverse

from constance import config
from constance.admin import ConstanceAdmin, Config

from carb import constants
from common.mail import send_mail

from .forms import ProcessConfigChangesConstanceForm, EmailUserChangeForm, EmailUserCreationForm
from .models import filter_inactive_group_queryset, User


def swap_title_fields(method):
    @wraps(method)
    def swapped(self, *args, **kwargs):
        fields = list(method(self, *args, **kwargs))
        try:
            title_index = fields.index('title')
        except ValueError:
            pass
        else:
            fields[title_index:title_index + 1] = self.model.TITLE_FIELDS
        return fields
    return swapped


class AudioAssetAdminBase(admin.ModelAdmin):
    add_fields = ('source', 'file', 'url', 'title')
    add_readonly_fields = ('uploader',)
    change_fields = ('title', 'file', 'duration', 'status', 'uploader', 'created', 'modified', 'task_log_line')
    change_readonly_fields = add_readonly_fields + ('duration', 'file', 'audio_player_html', 'status', 'created',
                                                    'modified', 'task_log_line')
    create_form = None
    date_hierarchy = 'created'
    list_display = ('title', 'created', 'duration', 'status')
    list_filter = (('uploader', admin.RelatedOnlyFieldListFilter), 'status')
    save_as_continue = False
    save_on_top = True
    search_fields = ('title',)

    class Media:
        js = ('common/admin/js/asset_source.js',)

    def has_change_permission(self, request, obj=None):
        return not (obj and obj.status != obj.Status.READY) and super().has_change_permission(request, obj=obj)

    @swap_title_fields
    def get_fields(self, request, obj=None):
        if obj is None:
            return self.add_fields
        else:
            fields = list(self.change_fields)
            if obj.file and obj.status == obj.Status.READY:
                file_index = fields.index('file')
                fields.insert(file_index, 'audio_player_html')
            else:
                fields.remove('file')

            # Remove these if they're falsey
            for field in ('duration', 'task_log_line'):
                if not getattr(obj, field):
                    fields.remove(field)

            return fields

    @swap_title_fields
    def get_readonly_fields(self, request, obj=None):
        return self.add_readonly_fields if obj is None else self.change_readonly_fields

    @swap_title_fields
    def get_list_display(self, request):
        return self.list_display

    @swap_title_fields
    def get_search_fields(self, request):
        return self.search_fields

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            kwargs['form'] = self.create_form
        return super().get_form(request, obj, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.uploader = request.user

        super().save_model(request, obj, form, change)

        if obj.run_download_after_save_url:
            messages.warning(request, f'The audio file is being downloaded from {obj.run_download_after_save_url}. '
                                      'Please refresh the page or come back later to check on its progress.')
        elif obj.run_conversion_after_save:
            messages.warning(request, f'The audio file is being converted to {config.ASSET_ENCODING} format. Please '
                                      'refresh the page or come back later to check on its progress.')


class HarborAuthListFilter(admin.SimpleListFilter):
    title = User._meta.get_field('harbor_auth').verbose_name
    parameter_name = 'harbor_auth'

    def lookups(self, request, model_admin):
        if config.GOOGLE_CALENDAR_ENABLED:
            return User.HarborAuth.choices
        else:
            return list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR, User.HarborAuth.choices))

    def queryset(self, request, queryset):
        if self.value():
            if not config.GOOGLE_CALENDAR_ENABLED and self.value() == User.HarborAuth.ALWAYS:
                return queryset.filter(harbor_auth__in=(User.HarborAuth.ALWAYS, User.HarborAuth.GOOGLE_CALENDAR))
            else:
                return queryset.filter(harbor_auth=self.value())


def send_set_password_email(request, user, newly_created=True):
    cache_token = secrets.token_urlsafe(12)  # It's signed, so doesn't need to be a very secure token
    # (<user id>, <newly created>, <cache_token>)
    # These links will function good for 12 hours (the duration of the cache key), at which point the user
    # will need to regenerate a new link in their inbox
    # The whole link itself is good for 14 days (or until it's used)
    cache.set(f'{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{cache_token}:usable', True, timeout=12 * 60 * 60)
    cache.set(f'{constants.CACHE_KEY_SET_PASSWORD_PREFIX}{cache_token}:valid', True, timeout=14 * 24 * 60 * 60)
    token = signing.dumps([user.id, newly_created, cache_token], salt='set:password', compress=True)
    url = request.build_absolute_uri(reverse('password_set_by_email', kwargs={'token': token}))

    if newly_created:
        subject = f'Welcome to {config.STATION_NAME}!'
        body = (f"Congratulations you've got a new account with {config.STATION_NAME}!\n\nThe username for the account "
                f'is: {user.username}\n\nTo set your password please go to the following URL: {url}')
    else:
        subject = f'Change Your Password on {config.STATION_NAME}'
        body = (f"To set a password for your account, please go to the following URL: {url}\n\nIn case you've "
                f'forgotten, the username for the account is: {user.username}')

    return send_mail(user.email, subject, body, request=request)


class UserAdmin(auth_admin.UserAdmin):
    save_on_top = True
    add_form_template = None
    add_form = EmailUserCreationForm
    form = EmailUserChangeForm
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth_pretty', 'is_active', 'is_superuser')
    list_filter = (HarborAuthListFilter, 'is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'modified', 'stream_key')

    class Media:
        js = ('common/admin/js/harbor_auth.js',)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (
                (None, {'fields': (('send_email',) if settings.EMAIL_ENABLED else ()) + (
                                    'username', 'email', 'password1', 'password2')}),
                ('Personal info', {'fields': (('first_name', 'last_name'), 'timezone')}),
                ('Permissions', {'fields': ('harbor_auth', ('gcal_entry_grace_minutes', 'gcal_exit_grace_minutes'),
                                            'is_superuser', 'groups')}),
                ('Additional info', {'fields': (('default_playlist',) if config.AUTODJ_ENABLED else ()) + (
                                                 'authorized_keys',)}),
            )
        else:
            return (
                (None, {'fields': (
                    ('send_email',) if settings.EMAIL_ENABLED else ()) + ('username', 'email', 'password')}),
                ('Personal info', {'fields': (('first_name', 'last_name'), 'timezone')}),
                ('Permissions', {'fields': ('harbor_auth', ('gcal_entry_grace_minutes', 'gcal_exit_grace_minutes'),
                                            'is_active', 'is_superuser', 'groups')}),
                ('Additional info', {'fields': (
                    ('default_playlist',) if config.AUTODJ_ENABLED else ()) + (
                     'authorized_keys',) + (('stream_key',) if settings.RTMP_ENABLED else ())}),
                ('Important dates', {'fields': ('last_login', 'date_joined', 'modified')}),
            )

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if not config.GOOGLE_CALENDAR_ENABLED and db_field.name == 'harbor_auth':
            kwargs['choices'] = list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR, User.HarborAuth.choices))
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        queryset = Group.objects.order_by('name')
        if db_field.name == 'groups':
            queryset = filter_inactive_group_queryset(queryset)
        kwargs['queryset'] = queryset
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['default_playlist'].widget.can_delete_related = False
        return form  # Delete widget was annoying me!

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if form.cleaned_data.get('send_email'):
            if send_set_password_email(request, obj, newly_created=not change):
                self.message_user(request,
                                  f'A an email has been sent to {obj.email} detailing how to set their password.')


class ProcessConfigChangesConstanceAdmin(ConstanceAdmin):
    change_list_form = ProcessConfigChangesConstanceForm


admin.site.unregister([Config])
admin.site.register([Config], ProcessConfigChangesConstanceAdmin)
admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
