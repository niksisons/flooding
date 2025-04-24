from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from django.shortcuts import render
from flooddata.views import HydrologicalCorrectionAPIView

# Простое представление для проверки работы сервера
def home(request):
    return render(request, 'home.html')

def map_view(request):
    return render(request, 'map.html')

# Импортируем представления, если они уже созданы
try:
    from flooddata.views import (FloodZoneViewSet, FloodEventViewSet, 
                              MeasurementPointViewSet, WaterLevelMeasurementViewSet)
    
    # Настройка REST API маршрутов
    router = DefaultRouter()
    router.register(r'flood-zones', FloodZoneViewSet)
    router.register(r'flood-events', FloodEventViewSet, basename='flood-event')
    router.register(r'measurement-points', MeasurementPointViewSet)
    router.register(r'water-levels', WaterLevelMeasurementViewSet, basename='water-level')
    # Добавляем новый endpoint для гидрологической коррекции DEM
    api_urls = [
        path('', include(router.urls)),
        path('auth/', obtain_auth_token, name='api_token_auth'),
        path('hydro-correction/', HydrologicalCorrectionAPIView.as_view(), name='hydro_correction'),
    ]
except ImportError:
    # Если представления еще не созданы, используем пустой список
    api_urls = []

urlpatterns = [
    path('', home, name='home'),  # Домашняя страница
    path('map/', map_view, name='map'),  # Страница с картой
    path('admin/', admin.site.urls),
    path('api/', include(api_urls)),
    path('api-auth/', include('rest_framework.urls')),
]

# Добавляем URL-шаблоны для статических и медиа-файлов
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)