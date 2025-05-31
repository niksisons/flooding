from osgeo import gdal, ogr, osr
import logging
import os
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.conf import settings
import numpy as np
from datetime import datetime
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape, mapping
import json

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

def hydrological_dem_correction(dem_path, output_dem_path=None, output_acc_path=None, already_filled=False):
    """
    Гидрологическая коррекция ЦМП (DEM) с помощью WhiteboxTools.
    Если already_filled=True, пропускает fill_depressions и сразу считает аккумуляцию.
    Args:
        dem_path: путь к исходному DEM (GeoTIFF)
        output_dem_path: путь для сохранения скорректированного DEM (опционально)
        output_acc_path: путь для сохранения карты аккумуляции (опционально)
        already_filled: если True, DEM уже заполнен (filled), не выполнять fill_depressions
    Returns:
        dict с numpy-массивами скорректированного DEM и аккумуляции
    """
    try:
        from whitebox.whitebox_tools import WhiteboxTools
        import numpy as np
        import rasterio
        import os
        wbt = WhiteboxTools()
        workdir = os.path.dirname(output_dem_path or dem_path)
        wbt.set_working_dir(workdir)
        filled_dem = output_dem_path or os.path.join(workdir, 'filled_dem_tmp.tif')
        acc_path = output_acc_path or os.path.join(workdir, 'accumulation_tmp.tif')
        if already_filled:
            # DEM уже заполнен, просто копируем файл если нужно
            if output_dem_path and dem_path != output_dem_path:
                import shutil
                shutil.copyfile(dem_path, output_dem_path)
            filled_dem = dem_path if not output_dem_path else output_dem_path
        else:
            wbt.fill_depressions(dem=dem_path, output=filled_dem)
        wbt.d8_flow_accumulation(i=filled_dem, output=acc_path)
        with rasterio.open(filled_dem) as src:
            filled = src.read(1)
        with rasterio.open(acc_path) as src:
            acc = src.read(1)
        return {
            'corrected_dem': filled,
            'accumulation': acc
        }
    except Exception as e:
        logger.error(f"Ошибка гидрологической коррекции DEM (whitebox): {str(e)}")
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

def process_satellite_image(satellite_image_path, output_mask_path=None, method='ndwi', threshold=0.2):
    """
    Обработка космического снимка для выделения водных объектов.
    Args:
        satellite_image_path: путь к космическому снимку (GeoTIFF, обычно многоканальный)
        output_mask_path: путь для сохранения маски воды (опционально)
        method: метод выделения воды ('ndwi', 'mndwi', 'awei', 'simple')
        threshold: пороговое значение для бинаризации
    Returns:
        dict с маской водных объектов и статистикой
    """
    try:
        with rasterio.open(satellite_image_path) as src:
            # Проверяем количество каналов и их наличие
            num_bands = src.count
            
            # Метод NDWI требует зеленый и ближний ИК каналы
            if method == 'ndwi':
                if num_bands < 2:
                    raise ValueError("Для NDWI требуются 2 канала (зеленый и ближний ИК)")
                green = src.read(1).astype(np.float32)
                nir = src.read(2).astype(np.float32)
                # Вычисляем NDWI
                ndwi = (green - nir) / (green + nir + 1e-10)
                # Бинаризация
                water_mask = (ndwi > threshold).astype(np.uint8)
            
            # Метод MNDWI требует зеленый и средний ИК каналы
            elif method == 'mndwi':
                if num_bands < 3:
                    raise ValueError("Для MNDWI требуются 3 канала (зеленый и средний ИК)")
                green = src.read(1).astype(np.float32)
                swir = src.read(3).astype(np.float32)
                # Вычисляем MNDWI
                mndwi = (green - swir) / (green + swir + 1e-10)
                # Бинаризация
                water_mask = (mndwi > threshold).astype(np.uint8)
            
            # Простой метод для RGB снимков
            elif method == 'simple':
                if num_bands < 3:
                    # Если один канал, используем его напрямую
                    if num_bands == 1:
                        band = src.read(1).astype(np.float32)
                        # Темные участки обычно вода
                        water_mask = (band < threshold * 255).astype(np.uint8)
                    else:
                        raise ValueError("Для простого метода требуется 1 или 3 канала")
                else:
                    # Используем RGB и вычисляем яркость
                    r = src.read(1).astype(np.float32)
                    g = src.read(2).astype(np.float32)
                    b = src.read(3).astype(np.float32)
                    # Средняя яркость
                    brightness = (r + g + b) / 3.0
                    # Темные участки обычно вода
                    water_mask = (brightness < threshold * 255).astype(np.uint8)
            else:
                raise ValueError(f"Неподдерживаемый метод выделения воды: {method}")
            
            # Сохраняем маску, если указан путь
            if output_mask_path:
                with rasterio.open(
                    output_mask_path, 'w',
                    driver='GTiff',
                    height=water_mask.shape[0],
                    width=water_mask.shape[1],
                    count=1,
                    dtype=water_mask.dtype,
                    crs=src.crs,
                    transform=src.transform
                ) as dst:
                    dst.write(water_mask, 1)
            
            # Вычисляем статистику
            water_pixels = int(water_mask.sum())
            total_pixels = water_mask.size
            water_percent = (water_pixels / total_pixels) * 100 if total_pixels > 0 else 0
            
            return {
                'water_mask': water_mask,
                'water_pixels': water_pixels,
                'total_pixels': total_pixels,
                'water_percent': water_percent,
                'mask_path': output_mask_path
            }
    
    except Exception as e:
        logger.error(f"Ошибка при обработке космического снимка: {str(e)}")
        raise

def create_flood_mask_vector(mask_path, output_vector_path=None, min_area=100):
    """
    Создает векторный слой из растровой маски затопления.
    Args:
        mask_path: путь к растровой маске затопления (GeoTIFF, 1 - вода, 0 - суша)
        output_vector_path: путь для сохранения векторного слоя (опционально)
        min_area: минимальная площадь полигона в пикселях
    Returns:
        dict с GeoJSON, площадью, количеством полигонов и путем к файлу
    """
    try:
        with rasterio.open(mask_path) as src:
            image = src.read(1)
            mask = (image == 1)
            # Проверка на пустую маску
            if not np.any(mask):
                logger.warning(f"Маска {mask_path} содержит только нули, векторизация невозможна.")
                return {
                    'vector_data': None,
                    'total_area_sqkm': 0.0,
                    'num_polygons': 0,
                    'vector_path': None
                }
            # Векторизация
            results = (
                {'properties': {'value': value}, 'geometry': s}
                for s, value in shapes(image, mask=mask, transform=src.transform)
                if value == 1
            )
            geoms = list(results)
            if not geoms:
                logger.warning(f"Векторизация: не найдено полигонов для {mask_path}")
                return {
                    'vector_data': None,
                    'total_area_sqkm': 0.0,
                    'num_polygons': 0,
                    'vector_path': None
                }
            gdf = gpd.GeoDataFrame.from_features(geoms, crs=src.crs)
            # Фильтрация по площади
            if 'geometry' in gdf.columns:
                gdf['area_px'] = gdf.geometry.area / abs(src.transform.a * src.transform.e)
                gdf = gdf[gdf.area_px > min_area]
            if gdf.empty:
                logger.warning(f"Векторизация: все полигоны меньше min_area для {mask_path}")
                return {
                    'vector_data': None,
                    'total_area_sqkm': 0.0,
                    'num_polygons': 0,
                    'vector_path': None
                }
            # Приведение CRS к EPSG:4326
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                try:
                    gdf = gdf.to_crs(epsg=4326)
                except Exception as e:
                    logger.error(f"Ошибка CRS при сохранении векторного слоя: {e}")
            gdf['area_sqkm'] = gdf.geometry.area / 1_000_000
            if output_vector_path:
                gdf.to_file(output_vector_path, driver='GeoJSON')
            total_area_sqkm = gdf['area_sqkm'].sum()
            geojson_str = gdf.to_json()
            return {
                'vector_data': geojson_str,
                'total_area_sqkm': float(total_area_sqkm),
                'num_polygons': len(gdf),
                'vector_path': output_vector_path
            }
    except Exception as e:
        logger.error(f"Ошибка при создании векторного слоя затопления: {str(e)}")
        raise

def calculate_flood_statistics(flood_vector_path, admin_boundaries_path=None):
    """
    Рассчитывает статистику затопления по административным границам.
    Args:
        flood_vector_path: путь к векторному слою затопления (GeoJSON)
        admin_boundaries_path: путь к векторному слою административных границ
    Returns:
        dict со статистикой затопления по районам
    """
    try:
        # Загружаем слой затопления
        flood_gdf = gpd.read_file(flood_vector_path)
        
        # Если нет слоя административных границ, возвращаем общую статистику
        if not admin_boundaries_path:
            total_area_sqkm = flood_gdf.geometry.area.sum() / 1_000_000
            return {
                'total_area_sqkm': float(total_area_sqkm),
                'num_polygons': len(flood_gdf)
            }
        
        # Загружаем слой административных границ
        admin_gdf = gpd.read_file(admin_boundaries_path)
        
        # Проверяем, что CRS одинаковые, иначе преобразуем
        if flood_gdf.crs != admin_gdf.crs:
            flood_gdf = flood_gdf.to_crs(admin_gdf.crs)
        
        # Выполняем пересечение и получаем статистику по районам
        stats = []
        for idx, admin_row in admin_gdf.iterrows():
            admin_geom = admin_row.geometry
            admin_name = admin_row.get('name', f'Район {idx+1}')
            
            # Вычисляем пересечение с затоплением
            intersection = flood_gdf.geometry.intersection(admin_geom)
            intersection_area = sum(geom.area for geom in intersection if not geom.is_empty) / 1_000_000
            
            # Общая площадь района
            admin_area = admin_geom.area / 1_000_000
            
            # Процент затопления
            flood_percent = (intersection_area / admin_area) * 100 if admin_area > 0 else 0
            
            stats.append({
                'admin_name': admin_name,
                'admin_area_sqkm': float(admin_area),
                'flood_area_sqkm': float(intersection_area),
                'flood_percent': float(flood_percent)
            })
        
        # Сортируем по проценту затопления в порядке убывания
        stats.sort(key=lambda x: x['flood_percent'], reverse=True)
        
        return {
            'admin_stats': stats,
            'total_area_sqkm': float(sum(item['flood_area_sqkm'] for item in stats))
        }
    
    except Exception as e:
        logger.error(f"Ошибка при расчете статистики затопления: {str(e)}")
        raise

def rasterize_waterbody_vector(vector_path, reference_raster_path, output_mask_path):
    """
    Растеризация векторного слоя водоёмов (shp/geojson) в бинарную маску (1 — вода, 0 — суша)
    Улучшено: CRS приводится к CRS снимка, обрезка по bbox снимка, логирование.
    Args:
        vector_path: путь к shp/geojson
        reference_raster_path: путь к растру-эталону (DEM или снимок)
        output_mask_path: путь для сохранения маски
    Returns:
        output_mask_path
    """
    import rasterio
    from rasterio.features import rasterize
    import geopandas as gpd
    with rasterio.open(reference_raster_path) as ref:
        transform = ref.transform
        out_shape = (ref.height, ref.width)
        crs = ref.crs
        bounds = ref.bounds
    gdf = gpd.read_file(vector_path)
    logger.info(f"Векторный слой: {vector_path}, CRS: {gdf.crs}, Число полигонов: {len(gdf)}")
    # Приведение CRS
    if gdf.crs != crs:
        gdf = gdf.to_crs(crs)
        logger.info(f"Векторный слой приведён к CRS снимка: {crs}")
    # Обрезка по bbox снимка
    bbox = (bounds.left, bounds.bottom, bounds.right, bounds.top)
    gdf_clip = gdf.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    logger.info(f"После обрезки по bbox: {bbox}, осталось полигонов: {len(gdf_clip)}")
    if gdf_clip.empty:
        logger.warning(f"Векторный слой после обрезки пуст. Маска будет нулевая.")
        mask = np.zeros(out_shape, dtype='uint8')
    else:
        shapes = ((geom, 1) for geom in gdf_clip.geometry if not geom.is_empty)
        mask = rasterize(
            shapes,
            out_shape=out_shape,
            transform=transform,
            fill=0,
            dtype='uint8'
        )
    with rasterio.open(
        output_mask_path, 'w',
        driver='GTiff',
        height=out_shape[0],
        width=out_shape[1],
        count=1,
        dtype='uint8',
        crs=crs,
        transform=transform
    ) as dst:
        dst.write(mask, 1)
    logger.info(f"Маска водоёмов сохранена: {output_mask_path}, уникальные значения: {np.unique(mask)}")
    return output_mask_path

def create_permanent_water_mask_from_accumulation(accumulation_path, output_mask_path, threshold=1000):
    """
    Создаёт маску постоянных вод (реки/озёра) по flow accumulation.
    Args:
        accumulation_path: путь к растру аккумуляции (GeoTIFF)
        output_mask_path: путь для сохранения маски
        threshold: пороговое значение аккумуляции
    Returns:
        output_mask_path
    """
    import rasterio
    import numpy as np
    with rasterio.open(accumulation_path) as src:
        acc = src.read(1)
        mask = (acc >= threshold).astype(np.uint8)
        profile = src.profile.copy()
        profile.update({'count': 1, 'dtype': 'uint8', 'nodata': 0})  # Явно задаём nodata для uint8
        with rasterio.open(output_mask_path, 'w', **profile) as dst:
            dst.write(mask, 1)
    return output_mask_path