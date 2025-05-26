# Заметки на полях: http://www.sen2waq.pl/
# https://creodias.eu/cases/monitoring-water-quality-using-python-and-sentinel-2-satellite-imagery/

# Спектральные индексы
# https://innoter.com/articles/vidy-vodnykh-indeksov-i-ikh-primenenie/

## Посмотрим на наши исходные данные 

import folium
import rasterio
from folium import raster_layers
from pyproj import Proj, transform
import numpy as np

# Путь к файлу изображения
image_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349/True_color_image.tif"

# Открываем изображение с помощью rasterio
with rasterio.open(image_path) as src:
    # Получаем геопривязку изображения в EPSG:32637
    bounds = src.bounds

    # Считываем изображение (3 канала: RGB)
    img_data = src.read([1, 2, 3]).transpose(1, 2, 0)

    # Преобразуем координаты из EPSG:32637 в EPSG:4326
    proj_utm = Proj(init='epsg:32637')  # Исходная система координат (UTM)
    proj_wgs = Proj(init='epsg:4326')   # Целевая система координат (WGS 84)

    # Преобразуем углы границ
    lon_min, lat_min = transform(proj_utm, proj_wgs, bounds[0], bounds[1])
    lon_max, lat_max = transform(proj_utm, proj_wgs, bounds[2], bounds[3])

    # Создаем карту, центрированную на центре изображения
    m = folium.Map(location=[(lat_min + lat_max) / 2, (lon_min + lon_max) / 2], zoom_start=10)

    # Добавляем изображение на карту с преобразованными координатами
    folium.raster_layers.ImageOverlay(
        image=img_data,
        bounds=[[lat_min, lon_min], [lat_max, lon_max]],  # Координаты в системе WGS 84
        colormap=lambda x: (x, x, x, 255),  # Простой colormap для цветной визуализации
        opacity=0.7
    ).add_to(m)

# Показываем карту
m

m.save("sentinel_2_color_krasnodar.html")


import rasterio
import numpy as np
import os
from rasterio.enums import Resampling

# Путь к папке с данными
folder_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349"

# Пути к файлам для Green (Band 3) и SWIR2 (Band 11)
green_path = os.path.join(folder_path, "Band_3_-_Green_-_10m.tif")
swir2_path = os.path.join(folder_path, "Band_11_-_SWIR_(1.6)_-_20m.tif")

# Чтение данных с использованием rasterio
with rasterio.open(green_path) as green_src:
    green = green_src.read(1)  # Считываем данные с первого канала (Green)
    green_transform = green_src.transform
    green_crs = green_src.crs
    green_shape = green.shape
    
target_width = green.shape[1]  # Ширина изображения Green
target_height = green.shape[0]  # Высота изображения Green
target_transform = green_transform  # Трансформация Green
green = green / green.max()

with rasterio.open(swir2_path) as swir2_src:
    # Применяем пересэмплирование с учетом целевых размеров и трансформации
    swir2 = swir2_src.read(1, out_shape=(target_height, target_width), resampling=Resampling.nearest)  # Применяем пересэмплирование
    swir2_transform = target_transform  # Применяем трансформацию от канала Green
    swir2_crs = swir2_src.crs  # Система координат (CRS) остается та же

swir2 = swir2 / swir2.max() 

# Проверяем размеры после пересэмплирования
if green.shape != swir2.shape:
    print(green.shape)
    print( swir2.shape)
    raise ValueError("Размеры изображений Green и SWIR2 не совпадают после пересэмплирования!")

# Расчет MNDWI
mndwi = (green - swir2) / (green + swir2)

# Сохраняем результат в новый файл (например, в GeoTIFF)
output_path = os.path.join(folder_path, "mndwi.tif")

# Запись результата в файл
with rasterio.open(output_path, 'w', driver='GTiff', 
                   count=1, dtype=mndwi.dtype, 
                   crs=green_crs, 
                   transform=green_transform, 
                   width=green.shape[1], height=green.shape[0]) as dst:
    dst.write(mndwi, 1)

print(f"MNDWI сохранен в файл {output_path}")


import rasterio
import matplotlib.pyplot as plt

# Путь к файлу MNDWI
mndwi_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349/mndwi.tif"

# Чтение данных из файла MNDWI
with rasterio.open(mndwi_path) as src:
    mndwi = src.read(1)  # Считываем первый (и единственный) канал

# Визуализация MNDWI с помощью matplotlib
plt.figure(figsize=(10, 10))
plt.imshow(mndwi, cmap='viridis', origin='upper')  # Используем цветовую карту 'viridis'
plt.colorbar()  # Добавляем цветовую шкалу
plt.title("MNDWI")  # Заголовок
plt.show()

import rasterio
import matplotlib.pyplot as plt
import numpy as np

# Пути к файлам
true_color_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349/True_color_image.tif"
mndwi_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349/mndwi.tif"

# Чтение изображений
with rasterio.open(true_color_path) as true_color_src:
    true_color = true_color_src.read([1, 2, 3])  # Чтение трех каналов (RGB)
    true_color = np.moveaxis(true_color, 0, -1)  # Переставляем оси для RGB

with rasterio.open(mndwi_path) as mndwi_src:
    mndwi = mndwi_src.read(1)  # Чтение первого канала MNDWI

# Создание маски для пикселей > 0 на MNDWI
mask = mndwi > 0

# Визуализация
fig, axs = plt.subplots(1, 3, figsize=(15, 5))

# Слева: True Color Image
axs[0].imshow(true_color)
axs[0].set_title("True Color Image")
axs[0].axis('off')  # Отключаем оси

# В центре: MNDWI
cax = axs[1].imshow(mndwi, cmap='viridis', origin='upper')
axs[1].set_title("MNDWI")
axs[1].axis('off')  # Отключаем оси
fig.colorbar(cax, ax=axs[1])  # Добавляем цветовую шкалу

# Справа: MNDWI с выделением пикселей > 0
highlighted_mndwi = mndwi.copy()
highlighted_mndwi[~mask] = np.nan  # Заменяем пиксели <= 0 на NaN, чтобы они не отображались
axs[2].imshow(highlighted_mndwi, cmap='viridis', origin='upper')
axs[2].set_title("MNDWI > 0")
axs[2].axis('off')  # Отключаем оси

plt.tight_layout()
plt.show()


# Учимся запрашивать объекты с OSM
# Откуда я знаю Тэги? Я читаю [сайты](https://taginfo.openstreetmap.org/)
import rasterio
import osmnx as ox
import geopandas as gpd
from pyproj import Proj, transform

# Путь к изображению (например, "True_color_image.tif")
image_path = "S2A_MSIL2A_20250109T082321_R121_T37TDM_20250109T112349/True_color_image.tif"

# Чтение геопривязки изображения с помощью rasterio
with rasterio.open(image_path) as src:
    # Получаем границы изображения в проекции EPSG:32637
    bounds = src.bounds  # (left, bottom, right, top)
    west, south, east, north = bounds

# Преобразуем координаты из EPSG:32637 в EPSG:4326 (широта, долгота)
proj_utm = Proj(init='epsg:32637')
proj_wgs84 = Proj(init='epsg:4326')

# Преобразуем координаты
west, south = transform(proj_utm, proj_wgs84, west, south)
east, north = transform(proj_utm, proj_wgs84, east, north)

# Запрос водных объектов в пределах указанных границ
tags = {'natural': 'water', 'waterway': True}

# Запрос водных объектов через osmnx
gdf_waterways = ox.geometries_from_bbox(north, south, east, west, tags)

# Фильтруем данные для выделения только водоемов и водных путей
gdf_waterways = gdf_waterways[gdf_waterways['geometry'].apply(lambda x: x.geom_type == 'Polygon' or x.geom_type == 'LineString')]

# Визуализация водных объектов
fig, ax = plt.subplots(figsize=(10, 10))
gdf_waterways.plot(ax=ax, color='blue', alpha=0.5)

# Добавляем настройки для отображения
ax.set_title("Water Bodies in the Area from Image")
plt.show()

gdf_waterways = gdf_waterways.applymap(lambda x: str(x) if isinstance(x, list) else x)

# Путь для сохранения GeoPackage
output_gpkg_path = "waterways.gpkg"

# Сохранение gdf_waterways в GeoPackage
gdf_waterways.to_file(output_gpkg_path, driver='GPKG')

print(f"GeoPackage сохранен в {output_gpkg_path}")

mport geopandas as gpd
import folium

# Загрузка GeoDataFrame из GeoPackage
gdf_waterways = gpd.read_file("waterways.gpkg")

# Создание карты с центром в первом объекте в gdf
m = folium.Map(location=[gdf_waterways.geometry.centroid.y.mean(), gdf_waterways.geometry.centroid.x.mean()], zoom_start=12)

# Добавление данных из GeoDataFrame как GeoJSON слой
folium.GeoJson(gdf_waterways).add_to(m)

# Отображение карты
m.save("map_with_waterways.html")



## Еще одна вариация на заданную тему (осторожно ,Ю работает долго, весит много)
import osmnx as ox
import geopandas as gpd

# Определяем границы Краснодарского края
place_name = "Краснодарский край, Россия"

# Загружаем дренажную систему (канавы, ручьи, реки, дренажные каналы) ["ditch", "drain", "stream", "river"]
tags = {"waterway": ["drain"]}
drainage = ox.features_from_place(place_name, tags)

# Сохраняем данные в Shapefile
shapefile_path = "drainage_krasnodar.shp"
drainage.to_file(shapefile_path, driver="ESRI Shapefile")

print(f"Данные сохранены в {shapefile_path}")