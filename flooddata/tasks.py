from background_task import background
from django.utils import timezone
from .models import FloodAnalysis
from .utils import process_satellite_image, create_flood_mask_vector
import os
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon as GEOSMultiPolygon
import json
import logging
import rasterio
import numpy as np
from rasterio.enums import Resampling
from skimage.measure import label
from shapely.geometry import shape, mapping
import geopandas as gpd
import traceback
from rasterio.warp import transform_bounds
from rasterio.windows import from_bounds

logger = logging.getLogger(__name__)

@background(schedule=1)
def process_flood_analysis_bg(analysis_id):
    analysis = None
    try:
        analysis = FloodAnalysis.objects.get(id=analysis_id)
        analysis.status = 'processing'
        analysis.save()
        dem_path = analysis.dem_file.file.path
        # Проверяем только нужные поля
        if not analysis.green_band_image or not analysis.swir2_band_image:
            raise Exception("Не выбраны оба снимка для анализа (Green и SWIR2)")
        green_path = analysis.green_band_image.file.path
        swir2_path = analysis.swir2_band_image.file.path
        output_dir = os.path.join(settings.MEDIA_ROOT, 'analysis_results')
        os.makedirs(output_dir, exist_ok=True)
        base_name = f"{analysis.id}_{analysis.name.replace(' ', '_')}"

        # --- 1. Маска воды по DEM (h < 0), обрезка по снимку ---
        with rasterio.open(green_path) as green_src:
            green_bounds = green_src.bounds
            green_crs = green_src.crs
            green_transform = green_src.transform
            target_shape = green_src.shape
        
        with rasterio.open(dem_path) as dem_src:
            dem_crs = dem_src.crs
            # Трансформируем bounds снимка в CRS DEM, если нужно
            if green_crs != dem_crs:
                dem_bounds = transform_bounds(green_crs, dem_crs, *green_bounds)
            else:
                dem_bounds = green_bounds
            # Получаем окно DEM, соответствующее снимку
            window = rasterio.windows.from_bounds(*dem_bounds, transform=dem_src.transform)
            window = window.round_offsets().round_lengths()
            # Читаем только нужную часть DEM
            dem = dem_src.read(1, window=window)
            # Обновляем профиль для обрезанного DEM
            dem_transform = rasterio.windows.transform(window, dem_src.transform)
            dem_profile = dem_src.profile.copy()
            dem_profile.update({
                'height': dem.shape[0],
                'width': dem.shape[1],
                'transform': dem_transform
            })
        dem_mask = (dem < 0).astype(np.uint8)
        dem_mask_path = os.path.join(output_dir, f"{base_name}_dem_water_mask.tif")
        dem_profile.update({'count': 1, 'dtype': 'uint8'})
        dem_profile.pop('nodata', None)  # Удаляем nodata для uint8 маски
        with rasterio.open(dem_mask_path, 'w', **dem_profile) as dst:
            dst.write(dem_mask, 1)

        # --- 2. Маска воды по снимку (MNDWI > 0) ---
        with rasterio.open(green_path) as green_src:
            green = green_src.read(1).astype(np.float32)
            green_transform = green_src.transform
            green_crs = green_src.crs
            target_shape = green.shape
        with rasterio.open(swir2_path) as swir2_src:
            swir2 = swir2_src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype(np.float32)
        green = green / np.max(green)
        swir2 = swir2 / np.max(swir2)
        mndwi = (green - swir2) / (green + swir2 + 1e-6)
        mndwi_mask = (mndwi > 0).astype(np.uint8)
        mndwi_mask_path = os.path.join(output_dir, f"{base_name}_mndwi_mask.tif")
        mndwi_profile = dem_profile.copy()
        mndwi_profile.update({"height": target_shape[0], "width": target_shape[1], "transform": green_transform, "crs": green_crs, "count": 1, "dtype": 'uint8'})
        with rasterio.open(mndwi_mask_path, 'w', **mndwi_profile) as dst:
            dst.write(mndwi_mask, 1)

        # --- 3. Приведение масок к одной сетке (если нужно) ---
        # Для простоты считаем, что green/mndwi уже в нужной сетке (как снимок)
        # DEM маску ресемплируем к размеру снимка
        if dem_mask.shape != mndwi_mask.shape:
            dem_mask_resampled = np.zeros_like(mndwi_mask)
            with rasterio.open(dem_mask_path) as src:
                rasterio.warp.reproject(
                    source=dem_mask,
                    destination=dem_mask_resampled,
                    src_transform=dem_profile['transform'],
                    src_crs=dem_profile['crs'],
                    dst_transform=green_transform,
                    dst_crs=green_crs,
                    resampling=Resampling.nearest
                )
            dem_mask = dem_mask_resampled

        # --- 4. Сравнение масок ---
        # 1 - вода только на DEM (исчезнувшая)
        # 2 - вода только на снимке (новая)
        # 3 - вода и там, и там (совпадает)
        only_dem = np.logical_and(dem_mask == 1, mndwi_mask == 0)
        only_mndwi = np.logical_and(dem_mask == 0, mndwi_mask == 1)
        both = np.logical_and(dem_mask == 1, mndwi_mask == 1)

        # --- 5. Векторизация и сохранение ---
        def mask_to_gdf(mask, transform, crs):
            shapes = list(rasterio.features.shapes(mask.astype(np.uint8), mask > 0, transform=transform))
            polygons = [shape(geom) for geom, val in shapes if val == 1]
            if not polygons:
                return gpd.GeoDataFrame({'geometry': []}, crs=crs)
            return gpd.GeoDataFrame({'geometry': polygons}, crs=crs)

        gdf_only_dem = mask_to_gdf(only_dem, green_transform, green_crs)
        gdf_only_mndwi = mask_to_gdf(only_mndwi, green_transform, green_crs)
        gdf_both = mask_to_gdf(both, green_transform, green_crs)

        # Сохраняем в GeoJSON
        only_dem_path = os.path.join(output_dir, f"{base_name}_only_dem.geojson")
        only_mndwi_path = os.path.join(output_dir, f"{base_name}_only_mndwi.geojson")
        both_path = os.path.join(output_dir, f"{base_name}_both.geojson")
        gdf_only_dem.to_file(only_dem_path, driver='GeoJSON')
        gdf_only_mndwi.to_file(only_mndwi_path, driver='GeoJSON')
        gdf_both.to_file(both_path, driver='GeoJSON')

        # --- 6. Считаем площади ---
        def area_sqkm(gdf):
            if gdf.empty:
                return 0.0
            # Переводим в метры, если нужно
            if gdf.crs.is_geographic:
                gdf = gdf.to_crs(epsg=3857)
            return float(gdf.area.sum() / 1e6)

        area_only_dem = area_sqkm(gdf_only_dem)
        area_only_mndwi = area_sqkm(gdf_only_mndwi)
        area_both = area_sqkm(gdf_both)

        # --- 7. Сохраняем результаты в FloodAnalysis ---
        analysis.status = 'completed'
        analysis.error_message = ''  # Очищаем сообщение об ошибке при успехе
        analysis.flooded_area_sqkm = area_only_mndwi + area_both  # Общая площадь воды по снимку
        analysis.dem_mask_path = dem_mask_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.mndwi_mask_path = mndwi_mask_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.only_dem_path = only_dem_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.only_mndwi_path = only_mndwi_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.both_path = both_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.area_only_dem = area_only_dem
        analysis.area_only_mndwi = area_only_mndwi
        analysis.area_both = area_both
        # Сохраняем flood_vector (совпадающая вода) в поле модели
        if not gdf_both.empty:
            # Переводим в WGS84, если нужно
            if gdf_both.crs and gdf_both.crs.to_string() != 'EPSG:4326':
                gdf_both = gdf_both.to_crs(epsg=4326)
            # Объединяем все полигоны в MultiPolygon
            multipoly = gdf_both.unary_union
            from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
            if multipoly.geom_type == 'Polygon':
                multipoly = MultiPolygon(GEOSGeometry(multipoly.wkt))
            else:
                multipoly = GEOSGeometry(multipoly.wkt)
            analysis.flood_vector = multipoly
        else:
            analysis.flood_vector = None
        analysis.save()
        logger.info(f"Анализ {analysis_id} успешно завершен. Площадь воды по снимку: {analysis.flooded_area_sqkm:.2f} км2")
    except Exception as e:
        error_message = f"Ошибка при обработке анализа затопления:\n{traceback.format_exc()}"
        logger.error(error_message)
        if analysis:
            analysis.status = 'error'
            analysis.error_message = error_message
            analysis.save() 