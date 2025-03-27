from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement
from .serializers import (FloodZoneSerializer, FloodEventSerializer,
                         MeasurementPointSerializer, WaterLevelMeasurementSerializer)

# Простой класс разрешений
class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated and request.user.is_staff

# Простые API представления - только основная функциональность для начала
class FloodZoneViewSet(viewsets.ModelViewSet):
    queryset = FloodZone.objects.all()
    serializer_class = FloodZoneSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name']

class FloodEventViewSet(viewsets.ModelViewSet):
    queryset = FloodEvent.objects.all()
    serializer_class = FloodEventSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['title']

class MeasurementPointViewSet(viewsets.ModelViewSet):
    queryset = MeasurementPoint.objects.all()
    serializer_class = MeasurementPointSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name', 'code']

class WaterLevelMeasurementViewSet(viewsets.ModelViewSet):
    queryset = WaterLevelMeasurement.objects.all()
    serializer_class = WaterLevelMeasurementSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['point', 'is_forecast']