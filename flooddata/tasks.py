from background_task import background
from django.utils import timezone
from .models import FloodAnalysis
from .utils import process_satellite_image, create_flood_mask_vector, rasterize_waterbody_vector, create_permanent_water_mask_from_accumulation, hydrological_dem_correction
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

        # --- 0. Маска постоянных вод (по выбору пользователя) ---
        permanent_water_method = analysis.permanent_water_method
        waterbody_vector = analysis.waterbody_vector
        accumulation_threshold = analysis.accumulation_threshold or 1000
        permanent_water_mask_path = None

        if permanent_water_method == 'accumulation':
            # --- Обрезка DEM по границе снимка для flow accumulation ---
            with rasterio.open(green_path) as green_src:
                green_bounds = green_src.bounds
                green_crs = green_src.crs
            with rasterio.open(dem_path) as dem_src: # Используем оригинальный DEM для обрезки
                dem_crs = dem_src.crs
                # Трансформируем bounds снимка в CRS DEM, если нужно
                if green_crs != dem_crs:
                    dem_bounds = transform_bounds(green_crs, dem_crs, *green_bounds)
                else:
                    dem_bounds = green_bounds
                
                # Округляем окно, чтобы избежать ошибок
                window = from_bounds(*dem_bounds, dem_src.transform).round_offsets().round_lengths()

                # Проверяем, что окно допустимо
                if window.width <= 0 or window.height <= 0 or window.col_off < 0 or window.row_off < 0:
                     raise ValueError("Недопустимые границы или окно для обрезки DEM.")

                dem_cropped = dem_src.read(1, window=window)
                dem_transform = rasterio.windows.transform(window, dem_src.transform)
                
                # Проверяем, что обрезанный DEM не пустой
                if dem_cropped.size == 0:
                     raise ValueError("Обрезанный DEM пустой.")

                dem_profile = dem_src.profile.copy()
                dem_profile.update({
                    'height': dem_cropped.shape[0],
                    'width': dem_cropped.shape[1],
                    'transform': dem_transform,
                    'compress': 'LZW' # Добавляем сжатие
                })
                cropped_dem_path = os.path.join(output_dir, f"{base_name}_dem_cropped.tif")
                dem_profile.update({'count': 1, 'dtype': 'float32'})
                with rasterio.open(cropped_dem_path, 'w', **dem_profile) as dst:
                    dst.write(dem_cropped, 1)
            
            # Используем обрезанный DEM и сохраняем accumulation в ту же папку analysis_results
            acc_path_output = os.path.join(output_dir, f"{base_name}_accumulation.tif")
            
            logger.info(f"Запуск hydrological_dem_correction для обрезанного DEM: {cropped_dem_path}")
            try:
                # Получаем объект DEMFile и определяем already_filled по is_base_layer
                dem_file_obj = analysis.dem_file
                already_filled = getattr(dem_file_obj, 'is_base_layer', False)
                # Передаем обрезанный DEM в hydrological_dem_correction с нужным флагом
                hydrological_dem_correction(cropped_dem_path, None, acc_path_output, already_filled=already_filled)
                logger.info(f"Создан файл аккумуляции: {acc_path_output}")
            except Exception as e:
                 logger.error(f"Ошибка при hydrological_dem_correction для {cropped_dem_path}: {e}")
                 raise # Перебрасываем ошибку дальше

            permanent_water_mask_path = os.path.join(output_dir, f"{base_name}_permanent_water_acc.tif")
            logger.info(f"Запуск create_permanent_water_mask_from_accumulation для {acc_path_output} с порогом {accumulation_threshold}")
            try:
                # Используем созданный файл аккумуляции для создания маски
                create_permanent_water_mask_from_accumulation(acc_path_output, permanent_water_mask_path, threshold=accumulation_threshold)
                logger.info(f"Создан файл растровой маски постоянных вод: {permanent_water_mask_path}")
                
                # Дополнительная проверка содержимого растровой маски
                if os.path.exists(permanent_water_mask_path):
                    with rasterio.open(permanent_water_mask_path) as src:
                         mask_data = src.read(1)
                         unique_values = np.unique(mask_data)
                         logger.info(f"Уникальные значения в маске постоянных вод {os.path.basename(permanent_water_mask_path)}: {unique_values}")
                         if len(unique_values) == 1 and unique_values[0] == 0:
                              logger.warning(f"Маска постоянных вод {os.path.basename(permanent_water_mask_path)} содержит только нули. Возможно, порог аккумуляции ({accumulation_threshold}) слишком высокий или данные DEM не подходят.")

            except Exception as e:
                 logger.error(f"Ошибка при create_permanent_water_mask_from_accumulation для {acc_path_output}: {e}")
                 raise # Перебрасываем ошибку дальше

            permanent_water_mask_type = 'accumulation' # Тип источника

        elif permanent_water_method == 'vector' and waterbody_vector:
            # Используем shp_file_path из модели WaterbodyVector
            vector_file_path = os.path.join(settings.MEDIA_ROOT, waterbody_vector.shp_file_path)
            permanent_water_mask_path = os.path.join(output_dir, f"{base_name}_permanent_water_vector.tif")
            logger.info(f"Запуск растеризации векторного слоя {vector_file_path}")
            try:
                # При растеризации вектора используем снимок как эталон по охвату и разрешению
                # Передаем путь к основному .shp файлу
                rasterize_waterbody_vector(vector_file_path, green_path, permanent_water_mask_path)
                logger.info(f"Создан файл растровой маски постоянных вод из вектора: {permanent_water_mask_path}")

                 # Дополнительная проверка содержимого растровой маски
                if os.path.exists(permanent_water_mask_path):
                    with rasterio.open(permanent_water_mask_path) as src:
                         mask_data = src.read(1)
                         unique_values = np.unique(mask_data)
                         logger.info(f"Уникальные значения в маске постоянных вод {os.path.basename(permanent_water_mask_path)}: {unique_values}")
                         if len(unique_values) == 1 and unique_values[0] == 0:
                              logger.warning(f"Растеризованная маска постоянных вод {os.path.basename(permanent_water_mask_path)} содержит только нули. Возможно, векторный слой пуст или не попадает в область снимка.")

            except Exception as e:
                 logger.error(f"Ошибка при растеризации векторного слоя {vector_file_path}: {e}")
                 raise # Перебрасываем ошибку дальше

            permanent_water_mask_type = 'vector' # Тип источника
        else:
             permanent_water_mask_path = None # Нет источника для постоянных вод
             permanent_water_mask_type = 'none'


        # --- 1. Маска воды по снимку (MNDWI > 0) ---
        # Этот шаг должен выполняться перед обработкой маски постоянных вод,
        # чтобы определить целевые размеры и CRS.
        logger.info("Начало расчета маски MNDWI")
        try:
            with rasterio.open(green_path) as green_src:
                green = green_src.read(1).astype(np.float32)
                green_transform = green_src.transform
                green_crs = green_src.crs
                target_shape = green.shape
            with rasterio.open(swir2_path) as swir2_src:
                # Ресемплинг снимка SWIR2 к размеру снимка Green
                swir2 = swir2_src.read(1, out_shape=target_shape, resampling=Resampling.nearest).astype(np.float32)
            
            # Нормализация снимков перед расчетом MNDWI
            max_green = np.max(green) if np.max(green) > 0 else 1 # Избегаем деления на ноль
            max_swir2 = np.max(swir2) if np.max(swir2) > 0 else 1 # Избегаем деления на ноль
            green_norm = green / max_green
            swir2_norm = swir2 / max_swir2

            mndwi = (green_norm - swir2_norm) / (green_norm + swir2_norm + 1e-6) # Добавляем epsilon для стабильности

            mndwi_mask = (mndwi > 0).astype(np.uint8)
            mndwi_mask_path = os.path.join(output_dir, f"{base_name}_mndwi_mask.tif")
            mndwi_profile = {
                'height': target_shape[0], 'width': target_shape[1], 'transform': green_transform, 'crs': green_crs, 'count': 1, 'dtype': 'uint8',
                 'compress': 'LZW' # Добавляем сжатие
            }
            with rasterio.open(mndwi_mask_path, 'w', **mndwi_profile) as dst:
                dst.write(mndwi_mask, 1)
            logger.info(f"Создана маска MNDWI: {mndwi_mask_path}")
            
            # Проверка содержимого маски MNDWI
            unique_mndwi_values = np.unique(mndwi_mask)
            logger.info(f"Уникальные значения в маске MNDWI: {unique_mndwi_values}")

        except Exception as e:
             logger.error(f"Ошибка при расчете маски MNDWI: {e}")
             raise # Перебрасываем ошибку дальше


        # --- 2. Маска постоянных вод (приведение к сетке снимка) ---
        # Теперь mndwi_mask определена и имеет нужные размеры и CRS.
        # Инициализируем pw_mask нулевой маской такого же размера, как mndwi_mask.
        pw_mask = np.zeros_like(mndwi_mask, dtype=np.uint8) 
        
        logger.info(f"Обработка маски постоянных вод. Источник: {permanent_water_mask_path}, Тип: {permanent_water_mask_type}")

        if permanent_water_mask_path and os.path.exists(permanent_water_mask_path):
            try:
                with rasterio.open(permanent_water_mask_path) as pw_src:
                    logger.info(f"Чтение растровой маски постоянных вод: {permanent_water_mask_path}")
                    
                    # Проверяем, что CRS совпадают или трансформируем
                    if pw_src.crs != green_crs:
                        logger.warning(f"CRS маски постоянных вод ({pw_src.crs}) не совпадает с CRS снимка ({green_crs}). Выполняем репроекцию.")
                        # Репроекция и ресемплинг маски постоянных вод к сетке снимка
                        reprojected_pw_mask = np.zeros_like(mndwi_mask, dtype=np.uint8)
                        from rasterio.warp import reproject
                        reproject(
                            source=pw_src.read(1),
                            destination=reprojected_pw_mask,
                            src_transform=pw_src.transform,
                            src_crs=pw_src.crs,
                            dst_transform=green_transform,
                            dst_crs=green_crs,
                            resampling=Resampling.nearest,
                            # Добавляем nodata, чтобы пустые области оставались 0
                            dst_nodata=0 
                        )
                        pw_mask = reprojected_pw_mask # Присваиваем значение
                        logger.info("Репроекция и ресемплинг маски постоянных вод завершены.")
                    elif pw_src.shape != mndwi_mask.shape:
                         logger.warning(f"Размер маски постоянных вод ({pw_src.shape}) не совпадает с размером снимка ({mndwi_mask.shape}). Выполняем ресемплинг.")
                         # Только ресемплинг, если CRS совпадает, но размер нет
                         resampled_pw_mask = np.zeros_like(mndwi_mask, dtype=np.uint8)
                         from rasterio.warp import reproject
                         reproject(
                            source=pw_src.read(1),
                            destination=resampled_pw_mask,
                            src_transform=pw_src.transform,
                            src_crs=pw_src.crs, # CRS совпадает
                            dst_transform=green_transform,
                            dst_crs=green_crs, # CRS совпадает
                            resampling=Resampling.nearest,
                            # Добавляем nodata
                            dst_nodata=0
                         )
                         pw_mask = resampled_pw_mask # Присваиваем значение
                         logger.info("Ресемплинг маски постоянных вод завершен.")
                    else:
                         # Размеры и CRS совпадают, просто читаем
                         pw_mask = pw_src.read(1) # Присваиваем значение
                         logger.info("Маска постоянных вод соответствует сетке снимка.")

                    # Проверка значений после приведения к сетке снимка
                    unique_pw_aligned_values = np.unique(pw_mask)
                    logger.info(f"Уникальные значения в маске постоянных вод после приведения к сетке снимка: {unique_pw_aligned_values}")

            except Exception as e:
                 logger.error(f"Ошибка при обработке маски постоянных вод {permanent_water_mask_path} после создания: {e}")
                 # В случае ошибки pw_mask останется нулевой, как инициализировано выше
                 pass # Не нужно присваивать pw_mask = np.zeros_like(...) здесь повторно


        # --- 3. Сравнение масок ---
        # 1 - вода только на постоянных водах (vector/accumulation) - ЗОНА ОСУШЕНИЯ (Пост. вода есть, снимок нет)
        # 2 - вода только на снимке (новая) - ЗОНА ЗАТОПЛЕНИЯ (Снимок есть, Пост. вода нет)
        # 3 - вода и там, и там (совпадает) - СОВПАДАЮЩАЯ ВОДА
        # Инвертируем pw_mask для корректного сравнения: 1 - пост. вода, 0 - не пост. вода
        # Теперь pw_mask гарантированно инициализирована
        pw_mask_binary = (pw_mask > 0).astype(np.uint8)
        mndwi_mask_binary = (mndwi_mask > 0).astype(np.uint8)

        logger.info("Выполнение сравнения масок: only_pw, only_mndwi, both")
        logger.info(f"Shape pw_mask_binary: {pw_mask_binary.shape}, Shape mndwi_mask_binary: {mndwi_mask_binary.shape}")

        # Зона осушения: Вода на пост. водах есть (1), на снимке нет (0)
        only_pw = np.logical_and(pw_mask_binary == 1, mndwi_mask_binary == 0).astype(np.uint8)
        logger.info(f"Уникальные значения в маске only_pw: {np.unique(only_pw)}")

        # Зона затопления: Вода на пост. водах нет (0), на снимке есть (1)
        only_mndwi = np.logical_and(pw_mask_binary == 0, mndwi_mask_binary == 1).astype(np.uint8)
        logger.info(f"Уникальные значения в маске only_mndwi: {np.unique(only_mndwi)}")

        # Совпадающая вода: Вода есть и там, и там (1 и 1)
        both = np.logical_and(pw_mask_binary == 1, mndwi_mask_binary == 1).astype(np.uint8)
        logger.info(f"Уникальные значения в маске both: {np.unique(both)}")


        # Функция для векторизации маски в GeoDataFrame
        def mask_to_gdf(mask_array, transform, crs):
            """Векторизует бинарную маску в GeoDataFrame."""
            from rasterio.features import shapes
            from shapely.geometry import shape
            from geopandas import GeoDataFrame

            logger.info(f"Начало векторизации маски с уникальными значениями: {np.unique(mask_array)}")

            # Получаем фигуры (полигоны) из маски, где значение пикселя > 0
            # Убедимся, что mask_array>0 действительно находит что-то
            if np.any(mask_array > 0):
                 all_shapes = shapes(mask_array, mask=mask_array > 0, transform=transform)
            else:
                 logger.warning("Векторизация: Маска содержит только нули.")
                 all_shapes = [] # Пустой итератор

            polygons = []
            for geom, value in all_shapes:
                if value > 0: # Учитываем только пиксели со значением > 0 (т.е. 1)
                    polygons.append(shape(geom))

            if not polygons:
                logger.warning("Векторизация: Не найдено полигонов для создания GeoDataFrame.")
                # Возвращаем пустой GeoDataFrame с правильным CRS
                return GeoDataFrame({'geometry': []}, crs=crs)

            # Создаем GeoDataFrame
            gdf = GeoDataFrame({'geometry': polygons}, crs=crs)

            # Если CRS не WGS84 (EPSG:4326), конвертируем для корректного сохранения в GeoJSON
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                 try:
                     gdf = gdf.to_crs(epsg=4326)
                     logger.info("GeoDataFrame сконвертирован в EPSG:4326.")
                 except Exception as e:
                     logger.error(f"Ошибка при конвертации CRS в EPSG:4326: {e}")
                     # Попробуем сохранить в исходном CRS, если конвертация не удалась
                     pass # Оставляем gdf как есть

            logger.info(f"Векторизация завершена. Создан GeoDataFrame с {len(polygons)} полигонами.")
            return gdf


        # Векторизуем каждую маску
        # Используем transform и crs от снимка (green_transform, green_crs)
        logger.info("Векторизация маски only_pw...")
        gdf_only_pw = mask_to_gdf(only_pw, green_transform, green_crs)
        logger.info("Векторизация маски only_mndwi...")
        gdf_only_mndwi = mask_to_gdf(only_mndwi, green_transform, green_crs)
        logger.info("Векторизация маски both...")
        gdf_both = mask_to_gdf(both, green_transform, green_crs)

        # Сохраняем в GeoJSON
        # Используем суффикс _pw для постоянных вод, чтобы не путать со старым only_dem
        only_pw_path_geojson = os.path.join(output_dir, f"{base_name}_only_pw.geojson") # Зона осушения
        only_mndwi_path_geojson = os.path.join(output_dir, f"{base_name}_only_mndwi.geojson") # Зона затопления
        both_path_geojson = os.path.join(output_dir, f"{base_name}_both.geojson") # Совпадающая вода

        logger.info(f"Сохранение GeoJSON: only_pw ({len(gdf_only_pw)} features), only_mndwi ({len(gdf_only_mndwi)} features), both ({len(gdf_both)} features)")

        try:
            gdf_only_pw.to_file(only_pw_path_geojson, driver='GeoJSON')
            logger.info(f"GeoJSON only_pw сохранен: {only_pw_path_geojson}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении only_pw GeoJSON: {e}")
            analysis.error_message += f"\nОшибка при сохранении only_pw GeoJSON: {e}"


        try:
            gdf_only_mndwi.to_file(only_mndwi_path_geojson, driver='GeoJSON')
            logger.info(f"GeoJSON only_mndwi сохранен: {only_mndwi_path_geojson}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении only_mndwi GeoJSON: {e}")
            analysis.error_message += f"\nОшибка при сохранении only_mndwi GeoJSON: {e}"

        try:
            gdf_both.to_file(both_path_geojson, driver='GeoJSON')
            logger.info(f"GeoJSON both сохранен: {both_path_geojson}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении both GeoJSON: {e}")
            analysis.error_message += f"\nОшибка при сохранении both GeoJSON: {e}"


        # Функция для расчета площади
        def area_sqkm(gdf):
            """Рассчитывает площадь GeoDataFrame в км², конвертируя в проекционную CRS."""
            if gdf.empty:
                logger.info("Расчет площади для пустого GeoDataFrame: 0.0 км²")
                return 0.0
            
            # Попытка использовать проекционную CRS, если gdf имеет CRS
            projected_gdf = gdf
            if gdf.crs and gdf.crs.is_geographic:
                try:
                    # Используем Web Mercator (EPSG:3857) как универсальную проекцию для площади
                    projected_gdf = gdf.to_crs(epsg=3857) 
                    logger.info("GeoDataFrame сконвертирован в EPSG:3857 для расчета площади.")
                except Exception as e:
                    logger.warning(f"Не удалось сконвертировать в EPSG:3857 для расчета площади: {e}. Расчет площади может быть неточным.")
                    # Если конвертация не удалась, считаем площадь в исходных координатах (будет неточно для WGS84)
                    pass

            # Рассчитываем сумму площадей всех полигонов и конвертируем в км²
            area = float(projected_gdf.area.sum() / 1e6)
            logger.info(f"Рассчитана площадь: {area:.2f} км²")
            return area

        logger.info("Расчет площадей...")
        area_only_pw = area_sqkm(gdf_only_pw)
        area_only_mndwi = area_sqkm(gdf_only_mndwi)
        area_both = area_sqkm(gdf_both)
        logger.info(f"Площади: only_pw={area_only_pw}, only_mndwi={area_only_mndwi}, both={area_both}")

        # --- 4. Сохраняем результаты в FloodAnalysis ---
        analysis.status = 'completed'
        analysis.error_message = ''
        analysis.flooded_area_sqkm = area_only_mndwi + area_both
        analysis.dem_mask_path = None
        analysis.mndwi_mask_path = mndwi_mask_path.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.only_dem_path = only_pw_path_geojson.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.only_mndwi_path = only_mndwi_path_geojson.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.both_path = both_path_geojson.replace(settings.MEDIA_ROOT, settings.MEDIA_URL)
        analysis.area_only_dem = area_only_pw
        analysis.area_only_mndwi = area_only_mndwi
        analysis.area_both = area_both
        # Сохраняем flood_vector (совпадающая вода) в поле модели
        if not gdf_both.empty:
            if gdf_both.crs and gdf_both.crs.to_string() != 'EPSG:4326':
                gdf_both = gdf_both.to_crs(epsg=4326)
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

        # --- 5. Генерируем PNG-карту с масками и сохраняем bounds ---
        from .utils import render_analysis_masks_png
        png_path = os.path.join(output_dir, f"{base_name}_map.png")
        bounds_json_path = os.path.join(output_dir, f"{base_name}_map_bounds.json")
        render_analysis_masks_png(
            only_pw_geojson=only_pw_path_geojson,
            only_mndwi_geojson=only_mndwi_path_geojson,
            both_geojson=both_path_geojson,
            output_png_path=png_path,
            bounds_json_path=bounds_json_path
        )
        logger.info(f"PNG-карта с масками сохранена: {png_path}, bounds: {bounds_json_path}")
    except Exception as e:
        error_message = f"Ошибка при обработке анализа затопления:\n{traceback.format_exc()}"
        logger.error(error_message)
        if analysis:
            analysis.status = 'error'
            analysis.error_message = error_message
            analysis.save()