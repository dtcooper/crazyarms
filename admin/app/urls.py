from django.contrib import admin
from django.urls import path

from carb import views

urlpatterns = [
    path('', views.StatusView.as_view(), name='status'),
    path('first-run/', views.FirstRunView.as_view(), name='first-run'),
    path('admin/', admin.site.urls),
]
