from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import D
from django.db.models import Q

from .models import FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement
from .serializers import (FloodZoneSerializer, FloodEventSerializer,
                         MeasurementPointSerializer, WaterLevelMeasurementSerializer)
from .permissions import IsAdminOrReadOnly

class FloodZoneViewSet(viewsets.ModelViewSet):
    queryset = FloodZone.objects.all()
    serializer_class = FloodZoneSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['risk_level']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'risk_level', 'created_at', 'updated_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class FloodEventViewSet(viewsets.ModelViewSet):
    serializer_class = FloodEventSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_forecast']
    search_fields = ['title', 'description']
    ordering_fields = ['event_start', 'water_level', 'created_at']
    
    def get_queryset(self):
        queryset = FloodEvent.objects.all()
        
        # Фильтрация по временному диапазону
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(event_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(
                Q(event_end__lte=end_date) | Q(event_end__isnull=True, event_start__lte=end_date)
            )
            
        # Фильтрация по актуальным событиям
        active = self.request.query_params.get('active', None)
        if active and active.lower() == 'true':
            now = timezone.now()
            queryset = queryset.filter(
                Q(event_start__lte=now) & (Q(event_end__gte=now) | Q(event_end__isnull=True))
            )
            
        return queryset
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Получить текущие события затопления"""
        now = timezone.now()
        events = FloodEvent.objects.filter(
            Q(event_start__lte=now) & (Q(event_end__gte=now) | Q(event_end__isnull=True))
        )
        serializer = self.get_serializer(events, many=True)
        return Response(serializer.data)
        
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class MeasurementPointViewSet(viewsets.ModelViewSet):
    queryset = MeasurementPoint.objects.all()
    serializer_class = MeasurementPointSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'created_at']
    
    @action(detail=False, methods=['get'])
    def nearby(self, request):
        """Найти ближайшие точки измерения к указанным координатам"""
        lon = request.query_params.get('lon', None)
        lat = request.query_params.get('lat', None)
        distance = request.query_params.get('distance', 10)  # В километрах
        
        if not (lon and lat):
            return Response({"error": "Необходимы параметры lon и lat"}, status=400)
            
        try:
            point = GEOSGeometry(f'POINT({lon} {lat})', srid=4326)
            points = MeasurementPoint.objects.filter(
                location__distance_lte=(point, D(km=float(distance)))
            ).distance(point).order_by('distance')
            
            serializer = self.get_serializer(points, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=400)

class WaterLevelMeasurementViewSet(viewsets.ModelViewSet):
    serializer_class = WaterLevelMeasurementSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['point', 'is_forecast']
    ordering_fields = ['timestamp', 'value']
    
    def get_queryset(self):
        queryset = WaterLevelMeasurement.objects.all()
        
        # Фильтрация по временному диапазону
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
            
        # Ограничение количества результатов для оптимизации
        limit = int(self.request.query_params.get('limit', 1000))
        return queryset[:limit]
        
    @action(detail=False, methods=['get'])
    def latest(self, request):
        """Получить последние измерения для каждой точки"""
        point_id = request.query_params.get('point', None)
        
        if point_id:
            # Для конкретной точки
            try:
                measurement = WaterLevelMeasurement.objects.filter(
                    point_id=point_id, is_forecast=False
                ).latest('timestamp')
                serializer = self.get_serializer(measurement)
                return Response(serializer.data)
            except WaterLevelMeasurement.DoesNotExist:
                return Response({"error": "Измерения не найдены"}, status=404)
        else:
            # Для всех точек
            from django.db.models import Max
            latest_ids = WaterLevelMeasurement.objects.filter(
                is_forecast=False
            ).values('point').annotate(
                latest_id=Max('id')
            ).values_list('latest_id', flat=True)
            
            measurements = WaterLevelMeasurement.objects.filter(id__in=latest_ids)
            serializer = self.get_serializer(measurements, many=True)
            return Response(serializer.data) 