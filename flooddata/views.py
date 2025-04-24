from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from .utils import hydrological_dem_correction
import os

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

class HydrologicalCorrectionAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        """
        Принимает путь к DEM-файлу (или файл), выполняет гидрологическую коррекцию и возвращает путь к результату.
        Пример запроса: { "dem_path": "/path/to/dem.tif" }
        """
        dem_path = request.data.get('dem_path')
        if not dem_path or not os.path.exists(dem_path):
            return Response({"error": "DEM файл не найден"}, status=status.HTTP_400_BAD_REQUEST)

        # Пути для сохранения результатов
        output_dir = os.path.join(settings.MEDIA_ROOT, 'dem_results')
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(dem_path))[0]
        corrected_path = os.path.join(output_dir, f"{base_name}_corrected.tif")
        acc_path = os.path.join(output_dir, f"{base_name}_accumulation.tif")

        try:
            result = hydrological_dem_correction(dem_path, corrected_path, acc_path)
            return Response({
                "corrected_dem": corrected_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL),
                "accumulation": acc_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL),
                "min_elevation": float(result['corrected_dem'].min()),
                "max_elevation": float(result['corrected_dem'].max()),
                "max_accumulation": float(result['accumulation'].max())
            })
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)