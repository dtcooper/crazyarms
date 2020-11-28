from functools import wraps

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group

from constance import config
from constance import admin as constance_admin

from .forms import ConstanceForm
from .models import User


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


class AudioAssetDownloadableAdminBase(admin.ModelAdmin):
    save_on_top = True
    create_form = None
    add_fields = ('source', 'file', 'url', 'title', 'status')
    change_fields = ('title', 'file', 'duration', 'status', 'uploader', 'task_log_line')
    add_readonly_fields = ('uploader', 'status')
    change_readonly_fields = add_readonly_fields + ('duration', 'file', 'audio_player_html', 'task_log_line')
    search_fields = ('title',)
    list_display = ('title', 'duration', 'status')
    list_filter = (('uploader', admin.RelatedOnlyFieldListFilter), 'status')

    class Media:
        js = ('common/admin/js/asset_source.js',)

    @swap_title_fields
    def get_fields(self, request, obj=None):
        if obj is None:
            return self.add_fields
        else:
            fields = list(self.change_fields)
            if obj.file:
                file_index = fields.index('file')
                fields.insert(file_index, 'audio_player_html')

            # Remove these if they're falsey
            for field in ('file', 'duration', 'task_log_line'):
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
        download_url = None
        if not change:
            obj.uploader = request.user
            if form.cleaned_data['source'] == 'url':
                download_url = form.cleaned_data['url']
                obj.title = f'Downloading {download_url}'

        super().save_model(request, obj, form, change)

        if download_url:
            messages.add_message(request, messages.WARNING,
                                 f'The audio file is being downloaded from {download_url}. Please refresh the page or '
                                 'come back later to check on its progress.')
            obj.queue_download(url=download_url, set_title=form.cleaned_data['title'])


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


class UserAdmin(auth_admin.UserAdmin):
    save_on_top = True
    add_form_template = None
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': (('first_name', 'last_name'), 'timezone')}),
        ('Permissions', {'fields': ('harbor_auth', ('google_calender_entry_grace_minutes',
                                    'google_calender_exit_grace_minutes'), 'is_active', 'is_superuser',
                                    'groups')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'modified')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth_pretty', 'is_superuser')
    list_filter = (HarborAuthListFilter, 'is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'modified')
    add_fieldsets = (
        (None, {'fields': ('username', 'email', 'password1', 'password2')}),
        ('Personal info', {'fields': (('first_name', 'last_name'), 'timezone')}),
        ('Permissions', {'fields': ('harbor_auth', ('google_calender_entry_grace_minutes',
                                    'google_calender_exit_grace_minutes'), 'is_superuser', 'groups')}),
    )

    class Media:
        js = ('common/admin/js/harbor_auth.js',)

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        if not config.GOOGLE_CALENDAR_ENABLED and db_field.name == 'harbor_auth':
            kwargs['choices'] = list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR, User.HarborAuth.choices))
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        queryset = Group.objects.order_by('name')
        if not settings.ZOOM_ENABLED and db_field.name == 'groups':
            queryset = queryset.exclude(permissions__codename='view_websockify')
        if not settings.HARBOR_TELNET_ENABLED and db_field.name == 'groups':
            queryset = queryset.exclude(permissions__codename='view_telnet')
        kwargs['queryset'] = queryset
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ConstanceAdmin(constance_admin.ConstanceAdmin):
    change_list_form = ConstanceForm


admin.site.unregister([constance_admin.Config])
admin.site.register([constance_admin.Config], ConstanceAdmin)
admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
