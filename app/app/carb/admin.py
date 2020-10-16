from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User

from constance import config

from .models import ScheduledGCalShow, UserProfile, ScheduledBroadcast


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'


class UserAdmin(DjangoUserAdmin):
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_superuser', 'groups',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_superuser')
    list_filter = ('is_superuser', 'is_active', 'groups')
    readonly_fields = ('last_login', 'date_joined')
    inlines = [UserProfileInline]

    def save_model(self, request, obj, form, change):
        obj.is_staff = True
        return super().save_model(request, obj, form, change)

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super(UserAdmin, self).get_inline_instances(request, obj)


class ScheduledGCalShowAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return config.GCAL_AUTH_ENABLED and super().has_view_permission(request, obj)


class ScheduledBroadcastAdmin(admin.ModelAdmin):
    fields = ('asset_path', 'scheduled_time', 'play_status', 'task_id')
    readonly_fields = ('play_status', 'task_id')

    def get_readonly_fields(self, request, obj=None):
        if obj:
            # Can only edit asset_path on creation
            return self.readonly_fields + ('asset_path',)
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.queue()


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
admin.site.register(ScheduledGCalShow, ScheduledGCalShowAdmin)
admin.site.register(ScheduledBroadcast, ScheduledBroadcastAdmin)
