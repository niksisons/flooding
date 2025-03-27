from django.contrib import admin
from django.contrib.gis.admin import OSMGeoAdmin
from .models import FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement

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