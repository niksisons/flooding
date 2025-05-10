from celery import shared_task
import logging
from django.utils import timezone
from datetime import timedelta
from .models import FloodEvent, MeasurementPoint, WaterLevelMeasurement, FloodAnalysis
from .utils import process_satellite_image, create_flood_mask_vector
import os
from django.conf import settings
from django.core.files import File
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon as GEOSMultiPolygon
import json

logger = logging.getLogger(__name__)

@shared_task
def update_geoserver_layers():
    """
    Задача для обновления слоев в GeoServer
    """
    logger.info("Запуск обновления слоев GeoServer")
    try:
        from .geoserver import setup_geoserver
        result = setup_geoserver()
        if result:
            logger.info("Обновление слоев GeoServer завершено успешно")
        else:
            logger.error("Ошибка при обновлении слоев GeoServer")
        return result
    except Exception as e:
        logger.error(f"Ошибка при обновлении слоев GeoServer: {str(e)}")
        return False

@shared_task
def update_water_level_data():
    """
    Задача для обновления данных об уровне воды.
    Это пример, реальная реализация будет зависеть от источника данных
    """
    logger.info("Запуск обновления данных об уровне воды")
    try:
        # Здесь должна быть логика получения данных из внешнего источника
        # Например, API гидрометцентра или собственных датчиков
        
        # Псевдокод для демонстрации:
        # new_data = fetch_data_from_external_api()
        # for item in new_data:
        #     point = MeasurementPoint.objects.get(code=item['station_code'])
        #     WaterLevelMeasurement.objects.create(
        #         point=point,
        #         timestamp=item['timestamp'],
        #         value=item['water_level'],
        #         is_forecast=False
        #     )
        
        logger.info("Обновление данных завершено успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении данных: {str(e)}")
        return False

@shared_task
def cleanup_old_forecast_data():
    """Удаление устаревших прогностических данных"""
    threshold_date = timezone.now() - timedelta(days=30)  # Например, старше 30 дней
    deleted, _ = WaterLevelMeasurement.objects.filter(
        is_forecast=True, timestamp__lt=threshold_date
    ).delete()
    logger.info(f"Удалено {deleted} устаревших прогностических записей")
    return deleted

@shared_task
def detect_flood_events():
    """
    Задача для автоматического определения событий затопления
    на основе данных об уровне воды
    """
    logger.info("Запуск определения событий затопления")
    try:
        # Логика анализа данных и создания событий
        # Пример: если уровень воды превышает пороговое значение 
        # в нескольких соседних точках, создаем новое событие
        
        # Псевдокод:
        # threshold = 5.0  # В метрах
        # points_exceeding = MeasurementPoint.objects.filter(
        #     measurements__value__gt=threshold,
        #     measurements__is_forecast=False,
        #     measurements__timestamp__gte=timezone.now() - timedelta(hours=24)
        # ).distinct()
        
        # if points_exceeding.count() >= 3:  # Если несколько точек показывают превышение
        #     # Создаем полигон на основе точек
        #     # ...
        #     FloodEvent.objects.create(
        #         title="Автоматически определенное затопление",
        #         geometry=polygon,
        #         event_start=timezone.now(),
        #         water_level=max_level,
        #         source="Автоматическое определение",
        #         is_forecast=False
        #     )
        
        logger.info("Определение событий завершено")
        return True
    except Exception as e:
        logger.error(f"Ошибка при определении событий: {str(e)}")
        return False 

@shared_task(bind=True, max_retries=3)
def process_flood_analysis(self, analysis_id):
    """
    Задача Celery для обработки анализа затопления
    """
    analysis = None
    try:
        analysis = FloodAnalysis.objects.get(id=analysis_id)
        
        # Обновляем статус
        analysis.status = 'processing'
        analysis.save()
        
        # Получаем пути к файлам
        dem_path = analysis.dem_file.file.path
        satellite_path = analysis.satellite_image.file.path
        
        # Проверяем существование файлов
        if not os.path.exists(dem_path):
            raise FileNotFoundError(f"DEM файл не найден: {dem_path}")
        if not os.path.exists(satellite_path):
            raise FileNotFoundError(f"Спутниковый снимок не найден: {satellite_path}")
        
        # Создаем директорию для результатов
        output_dir = os.path.join(settings.MEDIA_ROOT, 'analysis_results')
        os.makedirs(output_dir, exist_ok=True)
        
        base_name = f"{analysis.id}_{analysis.name.replace(' ', '_')}"
        mask_path = os.path.join(output_dir, f"{base_name}_water_mask.tif")
        vector_path = os.path.join(output_dir, f"{base_name}_flood_vector.geojson")
        
        # 1. Обрабатываем снимок для выделения воды
        logger.info(f"Начало обработки спутникового снимка: {satellite_path}")
        mask_result = process_satellite_image(satellite_path, mask_path, method='simple')
        logger.info("Обработка спутникового снимка завершена")
        
        # 2. Создаем векторный слой маски затопления
        logger.info(f"Начало создания векторного слоя: {mask_path}")
        vector_result = create_flood_mask_vector(mask_path, vector_path)
        logger.info("Создание векторного слоя завершено")
        
        # 3. Сохраняем результаты
        analysis.flood_mask.name = f"analysis_results/{base_name}_water_mask.tif"
        
        # 4. Обновляем статистику
        if vector_result['total_area_sqkm'] > 0:
            # Загружаем GeoJSON данные
            geojson_data = json.loads(vector_result['vector_data'])
            
            # Создаем MultiPolygon из всех полигонов
            polygons = []
            for feature in geojson_data['features']:
                geom = GEOSGeometry(json.dumps(feature['geometry']))
                polygons.append(geom)
            
            # Объединяем в MultiPolygon
            multi_polygon = GEOSMultiPolygon(polygons)
            
            # Сохраняем в модель
            analysis.flood_vector = multi_polygon
            analysis.flooded_area_sqkm = vector_result['total_area_sqkm']
        
        analysis.status = 'completed'
        analysis.save()
        logger.info(f"Анализ {analysis_id} успешно завершен")
        
        return True
        
    except Exception as e:
        error_message = f"Ошибка при обработке анализа затопления: {str(e)}"
        logger.error(error_message)
        if analysis:
            analysis.status = 'error'
            analysis.error_message = error_message
            analysis.save()
        
        # Пробуем повторить задачу
        try:
            self.retry(exc=e, countdown=60)  # Повторная попытка через 1 минуту
        except self.MaxRetriesExceededError:
            logger.error(f"Превышено максимальное количество попыток для анализа {analysis_id}")
            if analysis:
                analysis.error_message += "\nПревышено максимальное количество попыток"
                analysis.save()
            raise 