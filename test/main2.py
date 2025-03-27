import folium
import pandas as pd
from folium.plugins import HeatMap, Draw

# Функция для создания карты с начальными координатами
def create_map(start_coords, zoom_start=10):
    return folium.Map(location=start_coords, zoom_start=zoom_start, control_scale=True)

# Функция для добавления маркеров на карту
def add_markers_from_data(map_object, data, lat_col, lon_col, popup_col=None):
    for _, row in data.iterrows():
        lat, lon = row[lat_col], row[lon_col]
        popup = row[popup_col] if popup_col else "Точка данных"
        folium.Marker([lat, lon], popup=str(popup)).add_to(map_object)

# Функция для добавления тепловой карты
def add_heatmap(map_object, data, lat_col, lon_col):
    heat_data = [[row[lat_col], row[lon_col]] for _, row in data.iterrows()]
    HeatMap(heat_data).add_to(map_object)

# Чтение данных из CSV
file_path = "PKTeoricos_ADIF.csv"
data = pd.read_csv(file_path)

# Проверка первых строк данных
print("Первые строки данных:")
print(data.head())

# Укажите названия колонок с широтой и долготой
latitude_col = "lat"  # Убедитесь в правильности названия колонок!
longitude_col = "lon"
popup_col = "description" if "description" in data.columns else None

# Создание карты с начальными координатами
START_COORDS = [55.751244, 37.618423]  # Москва, если координаты не заданы
geoportal_map = create_map(START_COORDS)

# Добавляем маркеры и тепловую карту
add_markers_from_data(geoportal_map, data, latitude_col, longitude_col, popup_col)
add_heatmap(geoportal_map, data, latitude_col, longitude_col)

# Добавляем инструмент для рисования
Draw(export=True).add_to(geoportal_map)

# Сохраняем карту в HTML-файл
geoportal_map.save("geoportal_map_with_data.html")
print("Карта сохранена в geoportal_map_with_data.html")
