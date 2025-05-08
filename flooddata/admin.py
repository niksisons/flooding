from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import (FloodZone, FloodEvent, MeasurementPoint, 
                   WaterLevelMeasurement, DEMFile, SatelliteImage, FloodAnalysis)
from django.utils.html import format_html
from django.conf import settings
import os
from .utils import hydrological_dem_correction, process_satellite_image, create_flood_mask_vector

class MeasurementInline(admin.TabularInline):
    model = WaterLevelMeasurement
    extra = 1

@admin.register(MeasurementPoint)
class MeasurementPointAdmin(OSMGeoAdmin):
    list_display = ('name', 'code', 'get_location')
    search_fields = ('name', 'code')
    inlines = [MeasurementInline]
    
    def get_location(self, obj):
        if obj.location:
            return f"({obj.location.x:.4f}, {obj.location.y:.4f})"
        return "-"
    get_location.short_description = "Координаты"

@admin.register(FloodZone)
class FloodZoneAdmin(OSMGeoAdmin):
    list_display = ('name', 'risk_level', 'created_at', 'created_by')
    list_filter = ('risk_level', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(FloodEvent)
class FloodEventAdmin(OSMGeoAdmin):
    list_display = ('title', 'event_start', 'event_end', 'water_level', 'is_forecast', 'created_by')
    list_filter = ('is_forecast', 'event_start')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)

@admin.register(WaterLevelMeasurement)
class WaterLevelMeasurementAdmin(admin.ModelAdmin):
    list_display = ('point', 'timestamp', 'value', 'is_forecast')
    list_filter = ('point', 'timestamp', 'is_forecast')

@admin.register(DEMFile)
class DEMFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'upload_date', 'uploaded_by', 'is_active', 'is_base_layer')
    list_filter = ('upload_date', 'is_active', 'is_base_layer')
    search_fields = ('name', 'description')
    actions = ['run_hydro_correction', 'set_as_base_layer', 'deactivate_selected']

    def run_hydro_correction(self, request, queryset):
        for dem in queryset:
            base_name = os.path.splitext(os.path.basename(dem.file.name))[0]
            corrected_path = f"dem_results/{base_name}_corrected.tif"
            acc_path = f"dem_results/{base_name}_accumulation.tif"
            abs_corrected = os.path.join(settings.MEDIA_ROOT, corrected_path)
            abs_acc = os.path.join(settings.MEDIA_ROOT, acc_path)
            os.makedirs(os.path.dirname(abs_corrected), exist_ok=True)
            hydrological_dem_correction(dem.file.path, abs_corrected, abs_acc)
            self.message_user(request, f"Гидрологическая коррекция выполнена для {dem.name}")
    run_hydro_correction.short_description = "Выполнить гидрологическую коррекцию DEM"
    
    def set_as_base_layer(self, request, queryset):
        for dem in queryset:
            dem.is_base_layer = True
            dem.save()
        self.message_user(request, f"Выбрано {queryset.count()} файлов как базовые слои")
    set_as_base_layer.short_description = "Установить как базовый слой"
    
    def deactivate_selected(self, request, queryset):
        for dem in queryset:
            dem.is_active = False
            dem.save()
        self.message_user(request, f"Деактивировано {queryset.count()} файлов")
    deactivate_selected.short_description = "Деактивировать выбранные файлы"

@admin.register(SatelliteImage)
class SatelliteImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_date', 'upload_date', 'uploaded_by', 'status')
    list_filter = ('upload_date', 'image_date', 'status')
    search_fields = ('name', 'description')
    actions = ['process_satellite_images', 'mark_as_processed', 'mark_as_error']
    
    def process_satellite_images(self, request, queryset):
        for image in queryset:
            # Только для новых или с ошибкой
            if image.status not in ['new', 'error']:
                continue
                
            image.status = 'processing'
            image.save()
            
            try:
                # Получаем путь к файлу и создаем путь для маски
                image_path = image.file.path
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_dir = os.path.join(settings.MEDIA_ROOT, 'satellite_results')
                os.makedirs(output_dir, exist_ok=True)
                
                mask_path = os.path.join(output_dir, f"{base_name}_water_mask.tif")
                
                # Обрабатываем снимок для выделения воды
                process_satellite_image(image_path, mask_path, method='simple')
                
                image.status = 'completed'
                image.save()
                self.message_user(request, f"Обработан снимок: {image.name}")
            except Exception as e:
                image.status = 'error'
                image.save()
                self.message_user(request, f"Ошибка при обработке {image.name}: {str(e)}", level='ERROR')
    process_satellite_images.short_description = "Обработать космические снимки"
    
    def mark_as_processed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"Обновлен статус для {queryset.count()} снимков")
    mark_as_processed.short_description = "Отметить как обработанные"
    
    def mark_as_error(self, request, queryset):
        queryset.update(status='error')
        self.message_user(request, f"Обновлен статус для {queryset.count()} снимков")
    mark_as_error.short_description = "Отметить как ошибочные"

@admin.register(FloodAnalysis)
class FloodAnalysisAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'created_by', 'status', 'flooded_area_sqkm')
    list_filter = ('created_at', 'status', 'compared_with_base')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'flooded_area_sqkm')
    actions = ['process_analyses', 'mark_as_completed', 'create_flood_vectors']
    
    def process_analyses(self, request, queryset):
        for analysis in queryset:
            # Только для ожидающих или с ошибкой
            if analysis.status not in ['pending', 'error']:
                continue
                
            analysis.status = 'processing'
            analysis.save()
            
            try:
                # Получаем пути к файлам
                dem_path = analysis.dem_file.file.path
                satellite_path = analysis.satellite_image.file.path
                
                # Создаем директорию для результатов
                output_dir = os.path.join(settings.MEDIA_ROOT, 'analysis_results')
                os.makedirs(output_dir, exist_ok=True)
                
                base_name = f"{analysis.id}_{analysis.name.replace(' ', '_')}"
                mask_path = os.path.join(output_dir, f"{base_name}_water_mask.tif")
                vector_path = os.path.join(output_dir, f"{base_name}_flood_vector.geojson")
                
                # 1. Обрабатываем снимок для выделения воды
                mask_result = process_satellite_image(satellite_path, mask_path, method='simple')
                
                # 2. Создаем векторный слой маски затопления
                vector_result = create_flood_mask_vector(mask_path, vector_path)
                
                # 3. Сохраняем результаты
                from django.core.files import File
                analysis.flood_mask.name = f"analysis_results/{base_name}_water_mask.tif"
                
                # 4. Обновляем статистику
                if vector_result['total_area_sqkm'] > 0:
                    from django.contrib.gis.geos import GEOSGeometry
                    import json
                    
                    # Загружаем GeoJSON данные
                    geojson_data = json.loads(vector_result['vector_data'])
                    
                    # Создаем MultiPolygon из всех полигонов
                    polygons = []
                    for feature in geojson_data['features']:
                        geom = GEOSGeometry(json.dumps(feature['geometry']))
                        polygons.append(geom)
                    
                    # Объединяем в MultiPolygon
                    from django.contrib.gis.geos import MultiPolygon as GEOSMultiPolygon
                    multi_polygon = GEOSMultiPolygon(polygons)
                    
                    # Сохраняем в модель
                    analysis.flood_vector = multi_polygon
                    analysis.flooded_area_sqkm = vector_result['total_area_sqkm']
                
                analysis.status = 'completed'
                analysis.save()
                
                self.message_user(request, f"Анализ завершен: {analysis.name}")
            except Exception as e:
                analysis.status = 'error'
                analysis.error_message = str(e)
                analysis.save()
                self.message_user(request, f"Ошибка при обработке {analysis.name}: {str(e)}", level='ERROR')
    process_analyses.short_description = "Обработать выбранные анализы"
    
    def mark_as_completed(self, request, queryset):
        queryset.update(status='completed')
        self.message_user(request, f"Обновлен статус для {queryset.count()} анализов")
    mark_as_completed.short_description = "Отметить как завершенные"
    
    def create_flood_vectors(self, request, queryset):
        for analysis in queryset:
            if not analysis.flood_mask or not os.path.exists(analysis.flood_mask.path):
                self.message_user(request, f"Нет маски затопления для {analysis.name}", level='ERROR')
                continue
                
            try:
                vector_path = os.path.join(settings.MEDIA_ROOT, 
                                         f"analysis_results/{analysis.id}_flood_vector.geojson")
                
                # Создаем векторный слой маски затопления
                vector_result = create_flood_mask_vector(analysis.flood_mask.path, vector_path)
                
                if vector_result['total_area_sqkm'] > 0:
                    from django.contrib.gis.geos import GEOSGeometry
                    import json
                    
                    # Загружаем GeoJSON данные
                    geojson_data = json.loads(vector_result['vector_data'])
                    
                    # Создаем MultiPolygon из всех полигонов
                    polygons = []
                    for feature in geojson_data['features']:
                        geom = GEOSGeometry(json.dumps(feature['geometry']))
                        polygons.append(geom)
                    
                    # Объединяем в MultiPolygon
                    from django.contrib.gis.geos import MultiPolygon as GEOSMultiPolygon
                    multi_polygon = GEOSMultiPolygon(polygons)
                    
                    # Сохраняем в модель
                    analysis.flood_vector = multi_polygon
                    analysis.flooded_area_sqkm = vector_result['total_area_sqkm']
                    analysis.save()
                    
                    self.message_user(request, f"Создан векторный слой для {analysis.name}")
                else:
                    self.message_user(request, f"Нет полигонов затопления для {analysis.name}", level='WARNING')
            except Exception as e:
                self.message_user(request, f"Ошибка создания векторного слоя для {analysis.name}: {str(e)}", level='ERROR')
    create_flood_vectors.short_description = "Создать векторные слои затопления"