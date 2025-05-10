from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from django.conf import settings
from .utils import hydrological_dem_correction, compare_dem_with_satellite
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from .models import (FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement,
                    DEMFile, SatelliteImage, FloodAnalysis)
from django.core.serializers import serialize
from django.utils import timezone
import json
from django.urls import reverse
from .forms import (UserRegistrationForm, DEMFileUploadForm, 
                  SatelliteImageUploadForm, FloodAnalysisForm)

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

class CompareFloodMasksAPIView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        dem_path = request.data.get('dem_path')
        mask_path = request.data.get('mask_path')
        threshold = float(request.data.get('threshold', 2.0))
        if not (dem_path and mask_path and os.path.exists(dem_path) and os.path.exists(mask_path)):
            return Response({"error": "DEM или маска не найдены"}, status=status.HTTP_400_BAD_REQUEST)
        output_dir = os.path.join(settings.MEDIA_ROOT, 'dem_results')
        os.makedirs(output_dir, exist_ok=True)
        diff_path = os.path.join(output_dir, 'diff_map.tif')
        result = compare_dem_with_satellite(dem_path, mask_path, threshold, diff_output_path=diff_path)
        result['diff_map'] = diff_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        return Response(result)

def home(request):
    return render(request, "home.html")

def register_view(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f"Аккаунт создан для {username}. Теперь вы можете войти.")
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, "register.html", {"form": form})

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            messages.error(request, "Неверный логин или пароль")
    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def upload_view(request):
    """Представление с формами для загрузки DEM и космических снимков"""
    dem_form = DEMFileUploadForm()
    satellite_form = SatelliteImageUploadForm()
    
    # Получаем последние загрузки пользователя
    user_dem_files = DEMFile.objects.filter(uploaded_by=request.user).order_by('-upload_date')[:5]
    user_satellite_images = SatelliteImage.objects.filter(uploaded_by=request.user).order_by('-upload_date')[:5]
    
    context = {
        'dem_form': dem_form,
        'satellite_form': satellite_form,
        'user_dem_files': user_dem_files,
        'user_satellite_images': user_satellite_images,
    }
    
    return render(request, "upload.html", context)

@login_required
def upload_dem_file(request):
    """Обработчик загрузки DEM файла"""
    if request.method == "POST":
        form = DEMFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Сохраняем файл, но не фиксируем в базе
            dem_file = form.save(commit=False)
            dem_file.uploaded_by = request.user
            dem_file.save()
            
            messages.success(request, f"DEM файл '{dem_file.name}' успешно загружен")
            return redirect('upload')
        else:
            messages.error(request, "Ошибка при загрузке DEM файла")
    
    return redirect('upload')

@login_required
def upload_satellite_image(request):
    """Обработчик загрузки космического снимка"""
    if request.method == "POST":
        form = SatelliteImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Сохраняем файл, но не фиксируем в базе
            satellite_image = form.save(commit=False)
            satellite_image.uploaded_by = request.user
            satellite_image.save()
            
            messages.success(request, f"Космический снимок '{satellite_image.name}' успешно загружен")
            return redirect('upload')
        else:
            messages.error(request, "Ошибка при загрузке космического снимка")
    
    return redirect('upload')

@login_required
def analyze_view(request):
    """Представление для запуска анализа затопления"""
    if request.method == "POST":
        form = FloodAnalysisForm(request.POST, user=request.user)
        if form.is_valid():
            analysis = form.save(commit=False)
            analysis.created_by = request.user
            analysis.status = 'pending'
            analysis.save()
            
            # Запускаем задачу обработки в фоне через Celery
            from .tasks import process_flood_analysis
            process_flood_analysis.delay(analysis.id)
            
            messages.success(request, f"Анализ затопления '{analysis.name}' поставлен в очередь")
            return redirect('analysis_list')
    else:
        form = FloodAnalysisForm(user=request.user)
    
    context = {
        'form': form,
    }
    
    return render(request, "analyze.html", context)

@login_required
def analysis_list(request):
    """Список анализов затопления пользователя"""
    if request.user.is_staff:
        # Для админа показываем все анализы
        analyses = FloodAnalysis.objects.all().order_by('-created_at')
    else:
        # Для обычного пользователя - только его анализы
        analyses = FloodAnalysis.objects.filter(created_by=request.user).order_by('-created_at')
    
    context = {
        'analyses': analyses,
    }
    
    return render(request, "analysis_list.html", context)

@login_required
def analysis_detail(request, analysis_id):
    """Детальная информация о конкретном анализе затопления"""
    analysis = get_object_or_404(FloodAnalysis, pk=analysis_id)
    
    # Проверка прав доступа - только владелец или админ
    if analysis.created_by != request.user and not request.user.is_staff:
        messages.error(request, "У вас нет доступа к этому анализу")
        return redirect('analysis_list')
    
    context = {
        'analysis': analysis,
    }
    
    return render(request, "analysis_detail.html", context)

@login_required
def process_analysis(request, analysis_id):
    """Запуск обработки анализа"""
    try:
        analysis = get_object_or_404(FloodAnalysis, pk=analysis_id)
        
        # Проверка прав доступа - только владелец или админ
        if analysis.created_by != request.user and not request.user.is_staff:
            messages.error(request, "У вас нет прав для запуска этого анализа")
            return redirect('analysis_list')
        
        # Проверка статуса анализа
        if analysis.status not in ['pending', 'error']:
            messages.error(request, "Этот анализ уже обрабатывается или завершен")
            return redirect('analysis_detail', analysis_id=analysis_id)
        
        # Проверяем наличие необходимых файлов
        if not analysis.dem_file or not analysis.satellite_image:
            messages.error(request, "Отсутствуют необходимые файлы для анализа")
            return redirect('analysis_detail', analysis_id=analysis_id)
        
        # Обновляем статус перед запуском
        analysis.status = 'processing'
        analysis.error_message = ''
        analysis.save()
        
        # Запускаем задачу обработки в фоне через Celery
        from .tasks import process_flood_analysis
        task = process_flood_analysis.delay(analysis.id)
        
        # Сохраняем ID задачи для отслеживания
        analysis.task_id = task.id
        analysis.save()
        
        messages.success(request, f"Анализ '{analysis.name}' запущен в обработку")
        return redirect('analysis_detail', analysis_id=analysis_id)
        
    except Exception as e:
        logger.error(f"Ошибка при запуске анализа {analysis_id}: {str(e)}")
        messages.error(request, f"Произошла ошибка при запуске анализа: {str(e)}")
        return redirect('analysis_list')

@login_required
def check_analysis_status(request, analysis_id):
    """API endpoint для проверки статуса анализа"""
    analysis = get_object_or_404(FloodAnalysis, pk=analysis_id)
    
    # Проверка прав доступа
    if analysis.created_by != request.user and not request.user.is_staff:
        return JsonResponse({
            'error': 'У вас нет прав для просмотра этого анализа'
        }, status=403)
    
    return JsonResponse({
        'id': analysis.id,
        'name': analysis.name,
        'status': analysis.status,
        'error_message': analysis.error_message,
        'flooded_area_sqkm': analysis.flooded_area_sqkm,
        'created_at': analysis.created_at.isoformat(),
        'is_completed': analysis.status == 'completed',
        'has_error': analysis.status == 'error'
    })

# API для GeoJSON (для Leaflet)
def flood_zones_geojson(request):
    zones = FloodZone.objects.all()
    data = serialize('geojson', zones, geometry_field='geometry',
                   fields=('name', 'description', 'risk_level'))
    return JsonResponse(json.loads(data), safe=False)

def flood_events_geojson(request):
    events = FloodEvent.objects.all()
    data = serialize('geojson', events, geometry_field='geometry',
                   fields=('title', 'description', 'event_start', 'event_end', 'water_level', 'is_forecast'))
    return JsonResponse(json.loads(data), safe=False)

def measurement_points_geojson(request):
    points = MeasurementPoint.objects.all()
    data = serialize('geojson', points, geometry_field='location',
                   fields=('name', 'code', 'description'))
    return JsonResponse(json.loads(data), safe=False)

@login_required
def flood_analysis_geojson(request):
    """Возвращает GeoJSON с результатами анализа затопления для карты"""
    if request.user.is_staff:
        # Для админа показываем все завершенные анализы
        analyses = FloodAnalysis.objects.filter(
            status='completed', 
            flood_vector__isnull=False
        )
    else:
        # Для обычного пользователя - только его завершенные анализы
        analyses = FloodAnalysis.objects.filter(
            created_by=request.user,
            status='completed',
            flood_vector__isnull=False
        )
    
    data = serialize('geojson', analyses, geometry_field='flood_vector',
                   fields=('name', 'created_at', 'flooded_area_sqkm'))
    
    return JsonResponse(json.loads(data), safe=False)