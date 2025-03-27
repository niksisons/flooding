from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import FloodZone, FloodEvent, MeasurementPoint, WaterLevelMeasurement

class FloodZoneSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = FloodZone
        geo_field = "geometry"
        fields = ('id', 'name', 'description', 'risk_level', 'created_at', 'updated_at')

class FloodEventSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = FloodEvent
        geo_field = "geometry"
        fields = ('id', 'title', 'description', 'event_start', 'event_end', 
                  'water_level', 'source', 'is_forecast', 'created_at')

class MeasurementPointSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = MeasurementPoint
        geo_field = "location"
        fields = ('id', 'name', 'code', 'description', 'created_at')

class WaterLevelMeasurementSerializer(serializers.ModelSerializer):
    point_name = serializers.CharField(source='point.name', read_only=True)
    
    class Meta:
        model = WaterLevelMeasurement
        fields = ('id', 'point', 'point_name', 'timestamp', 'value', 'is_forecast') 