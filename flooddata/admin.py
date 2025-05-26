from django.contrib import admin
from .models import (FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement, DEMFile, SatelliteImage, FloodAnalysis)
from django.utils.html import format_html
from django.conf import settings
import os
from .utils import hydrological_dem_correction, process_satellite_image, create_flood_mask_vector

class MeasurementInline(admin.TabularInline):
    model = WaterLevelMeasurement
    extra = 1

@admin.register(MeasurementPoint)
class MeasurementPointAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'location')
    search_fields = ('name', 'code')
    inlines = [MeasurementInline]
    
    def get_location(self, obj):
        if obj.location:
            return f"({obj.location.x:.4f}, {obj.location.y:.4f})"
        return "-"
    get_location.short_description = "Координаты"

@admin.register(FloodZone)
class FloodZoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'risk_level', 'created_at', 'created_by')
    search_fields = ('name',)
    list_filter = ('risk_level',)

@admin.register(FloodEvent)
class FloodEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_start', 'event_end', 'water_level', 'is_forecast', 'created_by')
    search_fields = ('title',)
    list_filter = ('is_forecast',)

@admin.register(WaterLevelMeasurement)
class WaterLevelMeasurementAdmin(admin.ModelAdmin):
    list_display = ('point', 'timestamp', 'value', 'is_forecast')
    list_filter = ('is_forecast', 'timestamp')
    search_fields = ('point__name',)

@admin.register(DEMFile)
class DEMFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'upload_date', 'uploaded_by', 'is_active', 'is_base_layer')
    search_fields = ('name',)
    list_filter = ('is_active', 'is_base_layer')
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
    search_fields = ('name',)
    list_filter = ('status',)
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
    actions = []  # Удалены действия, связанные с Celery