from django.contrib import admin
from django.urls import path

from carb import views

urlpatterns = [
    path('', views.index, name='index'),
    path('first-run/', views.FirstRunView.as_view(), name='first-run'),
    path('admin/', admin.site.urls),
]
