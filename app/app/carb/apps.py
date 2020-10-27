from django.contrib.admin.apps import AdminConfig


class CARBAdminConfig(AdminConfig):
    default_site = 'carb.admin.CARBAdminSite'
