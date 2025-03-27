import folium
from folium.plugins import HeatMap, Draw
from shapely.geometry import Polygon, Point
import pandas as pd
from normalize import *
from geojson import *


# Начальные координаты карты
START_COORDS = [55.751244, 37.618423]  # Москва, например

# Создаем карту с начальными координатами
geoportal_map = folium.Map(location=START_COORDS, zoom_start=10, control_scale=True)

# Функция для добавления маркера на карту
def add_markers_from_data(map_object, data, lat_col, lon_col, popup_col=None):
    for _, row in data.iterrows():
        lat, lon = row[lat_col], row[lon_col]
        popup = row[popup_col] if popup_col else "Точка данных"
        folium.Marker([lat, lon], popup=str(popup)).add_to(map_object)

# Функция для добавления масок (полигонов)
def add_polygon(coords, color="red", fill_opacity=0.4):
    folium.Polygon(
        locations=coords,
        color=color,
        fill=True,
        fill_opacity=fill_opacity
    ).add_to(geoportal_map)

# Функция для добавления круга (например, проблемная зона)
def add_circle(lat, lon, radius, color="orange", popup_text="Проблемная зона"):
    folium.Circle(
        location=[lat, lon],
        radius=radius,
        color=color,
        fill=True,
        fill_opacity=0.5,
        popup=popup_text
    ).add_to(geoportal_map)

# Функция для добавления тепловой карты
def add_heatmap(map_object, data, lat_col, lon_col):
    heat_data = [[row[lat_col], row[lon_col]] for _, row in data.iterrows()]
    HeatMap(heat_data).add_to(map_object)

# Путь к GeoJSON файлу
file_pathjson = "geo.geojson"

# Обрабатываем данные
df_zones = process_geojson(file_pathjson)

# Сохраняем в CSV для дальнейшей работы
df_zones.to_csv("geo.csv", index=False)

file_path = "geo.csv"
# data = normalize_data(file_path)
data = pd.read_csv(file_path, index_col=0)
print("Первые строки данных:")
print(data.head())

# # Укажите названия колонок с широтой и долготой после нормализации
# latitude_col = "y"  # Столбец с широтой
# longitude_col = "x"  # Столбец с долготой
# popup_col = "description" if "description" in data.columns else None

# Укажите названия колонок с широтой и долготой после нормализации
latitude_col = "centroid_lat"  # Столбец с широтой
longitude_col = "centroid_lon"  # Столбец с долготой
popup_col = "description" if "description" in data.columns else None


# Пример обработки данных для нахождения проблемных мест
def find_problem_areas(data_points, threshold=2):
    """
    Обрабатывает список точек и возвращает проблемные зоны.
    Пример: проблемные зоны — области с количеством точек выше threshold.
    """
    problem_areas = []
    point_counts = {}

    # Подсчёт количества точек по координатам
    for point in data_points:
        key = (point[0], point[1])
        point_counts[key] = point_counts.get(key, 0) + 1

    # Выделяем проблемные зоны
    for coords, count in point_counts.items():
        if count >= threshold:
            problem_areas.append(coords)
    return problem_areas

add_markers_from_data(geoportal_map, data, latitude_col, longitude_col, popup_col)
add_heatmap(geoportal_map, data, latitude_col, longitude_col)




# Добавляем инструмент для рисования на карте
Draw(export=True).add_to(geoportal_map)

# Сохраняем карту в HTML-файл
geoportal_map.save("geoportal_map.html")
print("Карта сохранена в geoportal_map.html")


# Обработка данных и добавление проблемных зон
# problem_areas = find_problem_areas(data_points)
# for lat, lon in problem_areas:
#     add_circle(lat, lon, radius=500, color="red", popup_text="Проблемная зона")