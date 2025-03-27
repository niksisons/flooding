from django.core.management.base import BaseCommand
from django.contrib.gis.geos import GEOSGeometry
import json
import os
from flooddata.models import FloodZone
from django.conf import settings

class Command(BaseCommand):
    help = 'Импорт зон затопления из GeoJSON'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Путь к файлу GeoJSON')

    def handle(self, *args, **options):
        file_path = options['file_path']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f'Файл не найден: {file_path}'))
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                geojson_data = json.load(f)
                
            if geojson_data['type'] != 'FeatureCollection':
                self.stdout.write(self.style.ERROR('Неверный формат GeoJSON'))
                return
                
            count = 0
            for feature in geojson_data['features']:
                if feature['geometry']['type'] != 'Polygon':
                    continue
                    
                properties = feature.get('properties', {})
                name = properties.get('name', f'Зона затопления {count+1}')
                description = properties.get('description', '')
                risk_level = properties.get('risk_level', 1)
                
                # Преобразование геометрии
                geometry = GEOSGeometry(json.dumps(feature['geometry']))
                
                # Создание записи
                FloodZone.objects.create(
                    name=name,
                    description=description,
                    geometry=geometry,
                    risk_level=min(max(int(risk_level), 1), 3)
                )
                count += 1
                
            self.stdout.write(
                self.style.SUCCESS(f'Успешно импортировано {count} зон затопления')
            )
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка при импорте: {str(e)}')) 