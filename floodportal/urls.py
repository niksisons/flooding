from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from django.shortcuts import render
from flooddata.views import HydrologicalCorrectionAPIView
from flooddata.views import CompareFloodMasksAPIView
from flooddata import views

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
        path('compare-flood-masks/', CompareFloodMasksAPIView.as_view(), name='compare_flood_masks'),
    ]
except ImportError:
    # Если представления еще не созданы, используем пустой список
    api_urls = []

urlpatterns = [
    path('', views.home, name='home'),  # Домашняя страница
    path('map/', map_view, name='map'),  # Страница с картой
    path('admin/', admin.site.urls),
    path('api/', include(api_urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),  # Добавляем маршрут для регистрации
    path('upload/', views.upload_view, name='upload'),
    
    # Новые маршруты для работы с файлами и анализом
    path('upload/dem/', views.upload_dem_file, name='upload_dem'),
    path('upload/satellite/', views.upload_satellite_image, name='upload_satellite'),
    path('analyze/', views.analyze_view, name='analyze'),
    path('analyses/', views.analysis_list, name='analysis_list'),
    path('analyses/<int:analysis_id>/', views.analysis_detail, name='analysis_detail'),
    path('analyses/<int:analysis_id>/process/', views.process_analysis, name='process_analysis'),
    
    # GeoJSON API для карты
    path('geojson/flood-zones/', views.flood_zones_geojson, name='flood_zones_geojson'),
    path('geojson/flood-events/', views.flood_events_geojson, name='flood_events_geojson'),
    path('geojson/measurement-points/', views.measurement_points_geojson, name='measurement_points_geojson'),
    path('geojson/flood-analyses/', views.flood_analysis_geojson, name='flood_analysis_geojson'),

    # API endpoints
    path('api/flood-analysis/<int:analysis_id>/status/', views.check_analysis_status, name='check_analysis_status'),
    path('api/flood-analysis/<int:analysis_id>/geojson/', views.flood_analysis_geojson, name='flood_analysis_geojson'),
    path('api/flood-analysis/<int:analysis_id>/masks-geojson/', views.flood_analysis_masks_geojson, name='flood_analysis_masks_geojson'),
    path('api/flood-analyses-list/', views.flood_analyses_list, name='flood_analyses_list'),
]

# Добавляем URL-шаблоны для статических и медиа-файлов
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)