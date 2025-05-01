from osgeo import gdal, ogr, osr
import logging
import os
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.conf import settings
import numpy as np
from datetime import datetime

logger = logging.getLogger(__name__)

def convert_raster_to_vector(raster_path, threshold_value, output_path=None):
    """
    Конвертация растрового изображения в векторный полигон
    Args:
        raster_path: путь к растровому файлу
        threshold_value: пороговое значение для бинаризации
        output_path: путь для сохранения результата (опционально)
    Returns:
        GEOSGeometry объект с полигонами
    """
    try:
        # Открываем растр
        raster = gdal.Open(raster_path)
        band = raster.GetRasterBand(1)
        
        # Получаем данные и создаем маску по пороговому значению
        data = band.ReadAsArray()
        mask = data > threshold_value
        
        # Создаем временный растр для полигонизации
        driver = gdal.GetDriverByName('MEM')
        temp_raster = driver.Create('', raster.RasterXSize, 
                                  raster.RasterYSize, 1, gdal.GDT_Byte)
        temp_raster.SetGeoTransform(raster.GetGeoTransform())
        temp_raster.SetProjection(raster.GetProjection())
        temp_band = temp_raster.GetRasterBand(1)
        temp_band.WriteArray(mask.astype(np.uint8))
        
        # Создаем векторный слой
        driver = ogr.GetDriverByName('Memory')
        vector = driver.CreateDataSource('memory')
        srs = osr.SpatialReference()
        srs.ImportFromWkt(raster.GetProjection())
        layer = vector.CreateLayer('', srs, ogr.wkbMultiPolygon)
        
        # Полигонизация
        gdal.Polygonize(temp_band, None, layer, -1, [], callback=None)
        
        # Преобразуем в GEOSGeometry
        multipolygon = None
        for feature in layer:
            geom = feature.GetGeometryRef()
            if multipolygon is None:
                multipolygon = GEOSGeometry(geom.ExportToWkt())
            else:
                multipolygon = multipolygon.union(GEOSGeometry(geom.ExportToWkt()))
        
        # Сохраняем результат, если указан путь
        if output_path:
            driver = ogr.GetDriverByName('ESRI Shapefile')
            if os.path.exists(output_path):
                driver.DeleteDataSource(output_path)
            out_ds = driver.CreateDataSource(output_path)
            out_layer = out_ds.CreateLayer('', srs, ogr.wkbMultiPolygon)
            feature_defn = out_layer.GetLayerDefn()
            feature = ogr.Feature(feature_defn)
            feature.SetGeometry(ogr.CreateGeometryFromWkt(multipolygon.wkt))
            out_layer.CreateFeature(feature)
            out_ds = None
        
        return multipolygon
        
    except Exception as e:
        logger.error(f"Ошибка при конвертации растра в вектор: {str(e)}")
        raise

def calculate_flood_extent(measurement_points, interpolation_method='idw'):
    """
    Расчет области затопления на основе точек измерения
    Args:
        measurement_points: список точек измерения с уровнями воды
        interpolation_method: метод интерполяции ('idw' или 'kriging')
    Returns:
        GEOSGeometry объект с полигоном зоны затопления
    """
    try:
        # Создаем временный растр для интерполяции
        xmin = min(p.location.x for p in measurement_points)
        xmax = max(p.location.x for p in measurement_points)
        ymin = min(p.location.y for p in measurement_points)
        ymax = max(p.location.y for p in measurement_points)
        
        pixel_size = 0.001  # примерно 100м на экваторе
        width = int((xmax - xmin) / pixel_size)
        height = int((ymax - ymin) / pixel_size)
        
        # Создаем растр в памяти
        driver = gdal.GetDriverByName('MEM')
        raster = driver.Create('', width, height, 1, gdal.GDT_Float32)
        
        # Устанавливаем геопривязку
        geotransform = (xmin, pixel_size, 0, ymax, 0, -pixel_size)
        raster.SetGeoTransform(geotransform)
        
        # Устанавливаем проекцию (WGS 84)
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        raster.SetProjection(srs.ExportToWkt())
        
        # Выполняем интерполяцию
        if interpolation_method == 'idw':
            gdal.Grid(raster, 
                     [(p.location.x, p.location.y, p.value) for p in measurement_points],
                     algorithm='invdist')
        else:
            # Можно добавить другие методы интерполяции
            raise ValueError(f"Неподдерживаемый метод интерполяции: {interpolation_method}")
        
        # Конвертируем растр в полигоны
        return convert_raster_to_vector(raster, threshold_value=0)
        
    except Exception as e:
        logger.error(f"Ошибка при расчете области затопления: {str(e)}")
        raise

def export_flood_data(start_date, end_date, format='geojson'):
    """
    Экспорт данных о затоплениях в различные форматы
    Args:
        start_date: начальная дата
        end_date: конечная дата
        format: формат экспорта ('geojson', 'shp', 'kml')
    Returns:
        путь к файлу с экспортированными данными
    """
    try:
        from .models import FloodEvent
        
        # Получаем данные за период
        events = FloodEvent.objects.filter(
            event_start__gte=start_date,
            event_start__lte=end_date
        )
        
        # Создаем временную директорию для экспорта
        export_dir = os.path.join(settings.MEDIA_ROOT, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format == 'geojson':
            output_path = os.path.join(export_dir, f'flood_events_{timestamp}.geojson')
            driver = ogr.GetDriverByName('GeoJSON')
        elif format == 'shp':
            output_path = os.path.join(export_dir, f'flood_events_{timestamp}.shp')
            driver = ogr.GetDriverByName('ESRI Shapefile')
        elif format == 'kml':
            output_path = os.path.join(export_dir, f'flood_events_{timestamp}.kml')
            driver = ogr.GetDriverByName('KML')
        else:
            raise ValueError(f"Неподдерживаемый формат экспорта: {format}")
            
        # Создаем набор данных
        if os.path.exists(output_path):
            driver.DeleteDataSource(output_path)
        out_ds = driver.CreateDataSource(output_path)
        
        # Создаем слой
        srs = osr.SpatialReference()
        srs.ImportFromEPSG(4326)
        layer = out_ds.CreateLayer('flood_events', srs, ogr.wkbMultiPolygon)
        
        # Добавляем поля
        layer.CreateField(ogr.FieldDefn('title', ogr.OFTString))
        layer.CreateField(ogr.FieldDefn('start_date', ogr.OFTDateTime))
        layer.CreateField(ogr.FieldDefn('water_level', ogr.OFTReal))
        
        # Добавляем данные
        for event in events:
            feature = ogr.Feature(layer.GetLayerDefn())
            feature.SetField('title', event.title)
            feature.SetField('start_date', event.event_start.strftime('%Y-%m-%d %H:%M:%S'))
            feature.SetField('water_level', float(event.water_level) if event.water_level else 0.0)
            
            # Устанавливаем геометрию
            geom = ogr.CreateGeometryFromWkt(event.geometry.wkt)
            feature.SetGeometry(geom)
            layer.CreateFeature(feature)
            
        out_ds = None
        return output_path
        
    except Exception as e:
        logger.error(f"Ошибка при экспорте данных: {str(e)}")
        raise

def hydrological_dem_correction(dem_path, output_dem_path=None, output_acc_path=None):
    """
    Гидрологическая коррекция ЦМП (DEM) с помощью pysheds.
    Args:
        dem_path: путь к исходному DEM (GeoTIFF)
        output_dem_path: путь для сохранения скорректированного DEM (опционально)
        output_acc_path: путь для сохранения карты аккумуляции (опционально)
    Returns:
        dict с numpy-массивами скорректированного DEM и аккумуляции
    """
    try:
        from pysheds.grid import Grid
        import numpy as np
        import os
        
        grid = Grid.from_raster(dem_path)
        dem = grid.read_raster(dem_path)

        # 1. Fill pits
        pit_filled_dem = grid.fill_pits(dem)
        # 2. Fill depressions
        flooded_dem = grid.fill_depressions(pit_filled_dem)
        # 3. Resolve flats
        inflated_dem = grid.resolve_flats(flooded_dem)
        # 4. Flow direction
        fdir = grid.flowdir(inflated_dem)
        # 5. Accumulation
        acc = grid.accumulation(fdir)

        # Сохраняем скорректированный DEM
        if output_dem_path:
            grid.save_raster(output_dem_path, inflated_dem, dtype='float32')
        # Сохраняем аккумуляцию
        if output_acc_path:
            grid.save_raster(output_acc_path, acc, dtype='float32')

        return {
            'corrected_dem': inflated_dem,
            'accumulation': acc
        }
    except Exception as e:
        logger.error(f"Ошибка гидрологической коррекции DEM: {str(e)}")
        raise

def compare_dem_with_satellite(dem_path, satellite_mask_path, threshold=2.0, diff_output_path=None):
    """
    Сравнение DEM (скорректированного) с маской затопления по ДЗЗ.
    dem_path: путь к скорректированному DEM (GeoTIFF)
    satellite_mask_path: путь к бинарной маске затопления по ДЗЗ (GeoTIFF, 1 - затоплено, 0 - нет)
    threshold: высота, ниже которой считается потенциальное затопление
    diff_output_path: путь для сохранения карты различий (опционально)
    Возвращает: dict с IoU, false positives, false negatives, путь к карте различий
    """
    import rasterio
    import numpy as np
    import os
    
    with rasterio.open(dem_path) as dem_src, rasterio.open(satellite_mask_path) as mask_src:
        dem = dem_src.read(1)
        mask = mask_src.read(1)
        # Приведение к одной размерности, если нужно
        if dem.shape != mask.shape:
            raise ValueError("Размеры DEM и маски не совпадают")
    
    # Маска потенциальных затоплений по DEM
    dem_flood = (dem < threshold).astype(np.uint8)
    # False positives: по ДЗЗ есть вода, по DEM нет
    false_positives = (mask == 1) & (dem_flood == 0)
    # False negatives: по DEM должно быть затопление, по ДЗЗ нет
    false_negatives = (mask == 0) & (dem_flood == 1)
    # True positives: совпадения
    true_positives = (mask == 1) & (dem_flood == 1)
    # IoU
    intersection = np.logical_and(mask == 1, dem_flood == 1).sum()
    union = np.logical_or(mask == 1, dem_flood == 1).sum()
    iou = intersection / union if union > 0 else 0
    # Карта различий: 0 - совпадение, 1 - FP, 2 - FN
    diff_map = np.zeros_like(mask, dtype=np.uint8)
    diff_map[false_positives] = 1
    diff_map[false_negatives] = 2
    # Сохраняем карту различий
    if diff_output_path:
        with rasterio.open(
            diff_output_path, 'w',
            driver='GTiff',
            height=diff_map.shape[0],
            width=diff_map.shape[1],
            count=1,
            dtype=diff_map.dtype,
            crs=dem_src.crs,
            transform=dem_src.transform
        ) as dst:
            dst.write(diff_map, 1)
    return {
        'iou': float(iou),
        'false_positives': int(false_positives.sum()),
        'false_negatives': int(false_negatives.sum()),
        'diff_map': diff_output_path
    }