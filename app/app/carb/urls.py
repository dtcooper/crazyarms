from django.contrib import admin
from django.urls import include, path
from django.utils.safestring import mark_safe

from constance import config


admin.site.site_title = admin.site.site_header = lambda: f'{config.STATION_NAME} admin'
admin.site.index_title = 'Station administration'
admin.site.empty_value_display = mark_safe('<em>none</em>')

urlpatterns = [
    path('', include('webui.urls')),
    path('api/', include('api.urls')),
    path('admin/', admin.site.urls),
]
