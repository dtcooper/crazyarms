from django.contrib.admin.apps import AdminConfig


class CrazyArmsAdminConfig(AdminConfig):
    default_site = "crazyarms.admin.CrazyArmsAdminSite"
