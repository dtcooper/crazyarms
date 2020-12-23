from functools import wraps

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group

from constance import config
from constance import admin as constance_admin

from .forms import ConstanceForm
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
        ('Additional credentials', {'fields': ('authorized_keys',) + (
            ('stream_key',) if settings.RTMP_ENABLED else ())}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth_pretty', 'is_superuser')
    list_filter = (HarborAuthListFilter, 'is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'modified', 'stream_key')
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
        if db_field.name == 'groups':
            queryset = filter_inactive_group_queryset(queryset)
        kwargs['queryset'] = queryset
        return super().formfield_for_manytomany(db_field, request, **kwargs)


class ConstanceAdmin(constance_admin.ConstanceAdmin):
    change_list_form = ConstanceForm


admin.site.unregister([constance_admin.Config])
admin.site.register([constance_admin.Config], ConstanceAdmin)
admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
