from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement, DEMFile
from .utils import hydrological_dem_correction
import os
from django.conf import settings

@admin.register(FloodZone)
class FloodZoneAdmin(OSMGeoAdmin):
    list_display = ('name', 'risk_level', 'created_at', 'updated_at')
    list_filter = ('risk_level', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(FloodEvent)
class FloodEventAdmin(OSMGeoAdmin):
    list_display = ('title', 'event_start', 'event_end', 'water_level', 'is_forecast')
    list_filter = ('is_forecast', 'event_start', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)

@admin.register(MeasurementPoint)
class MeasurementPointAdmin(OSMGeoAdmin):
    list_display = ('name', 'code', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at',)

@admin.register(WaterLevelMeasurement)
class WaterLevelMeasurementAdmin(admin.ModelAdmin):
    list_display = ('point', 'timestamp', 'value', 'is_forecast')
    list_filter = ('is_forecast', 'timestamp', 'point')
    search_fields = ('point__name', 'point__code')

@admin.register(DEMFile)
class DEMFileAdmin(admin.ModelAdmin):
    list_display = ('file', 'uploaded_at', 'processed')
    actions = ['run_hydro_correction']

    def run_hydro_correction(self, request, queryset):
        for dem in queryset:
            if not dem.processed:
                base_name = os.path.splitext(os.path.basename(dem.file.name))[0]
                corrected_path = f"dem_results/{base_name}_corrected.tif"
                acc_path = f"dem_results/{base_name}_accumulation.tif"
                abs_corrected = os.path.join(settings.MEDIA_ROOT, corrected_path)
                abs_acc = os.path.join(settings.MEDIA_ROOT, acc_path)
                os.makedirs(os.path.dirname(abs_corrected), exist_ok=True)
                hydrological_dem_correction(dem.file.path, abs_corrected, abs_acc)
                dem.corrected_file.name = corrected_path
                dem.accumulation_file.name = acc_path
                dem.processed = True
                dem.save()
    run_hydro_correction.short_description = "Выполнить гидрологическую коррекцию DEM"