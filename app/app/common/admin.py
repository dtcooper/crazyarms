from django.contrib import admin
from django.contrib.auth import admin as auth_admin
from django.contrib.auth.models import Group

from constance import config
from constance import admin as constance_admin

from .forms import ConstanceForm
from .models import User


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
                                    'google_calender_exit_grace_minutes'), 'is_active', 'is_staff', 'is_superuser',
                                    'groups')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'modified')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'harbor_auth_pretty', 'is_staff')
    list_filter = (HarborAuthListFilter, 'is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined', 'modified')
    add_fieldsets = (
        (None, {'fields': ('username', 'email', 'password1', 'password2')}),
        ('Personal info', {'fields': (('first_name', 'last_name'), 'timezone')}),
        ('Permissions', {'fields': ('harbor_auth', ('google_calender_entry_grace_minutes',
                                    'google_calender_exit_grace_minutes'), 'is_staff', 'is_superuser', 'groups')}),
    )

    class Media:
        js = ('common/admin/js/harbor_auth.js',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not config.GOOGLE_CALENDAR_ENABLED:
            harbor_auth_field = form.base_fields['harbor_auth']
            harbor_auth_field.choices = list(filter(lambda c: c[0] != User.HarborAuth.GOOGLE_CALENDAR,
                                                    harbor_auth_field.choices))
        return form


class ConstanceAdmin(constance_admin.ConstanceAdmin):
    change_list_form = ConstanceForm


admin.site.unregister([constance_admin.Config])
admin.site.register([constance_admin.Config], ConstanceAdmin)
admin.site.register(User, UserAdmin)
admin.site.unregister(Group)
