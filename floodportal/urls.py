from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from flooddata.views import (FloodZoneViewSet, FloodEventViewSet, 
                           MeasurementPointViewSet, WaterLevelMeasurementViewSet)

router = DefaultRouter()
router.register(r'flood-zones', FloodZoneViewSet)
router.register(r'flood-events', FloodEventViewSet, basename='flood-event')
router.register(r'measurement-points', MeasurementPointViewSet)
router.register(r'water-levels', WaterLevelMeasurementViewSet, basename='water-level')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('api-token-auth/', obtain_auth_token, name='api_token_auth'),
] 