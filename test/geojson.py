import json
import pandas as pd
from shapely.geometry import shape

def process_geojson(file_path):

    # Открываем и загружаем GeoJSON файл
    with open(file_path, encoding="utf-8") as f:
        geojson_data = json.load(f)

    # Проверка типа данных GeoJSON
    if geojson_data["type"] != "FeatureCollection":
        raise ValueError("Неверный формат GeoJSON: ожидается 'FeatureCollection'.")

    # Список для сбора данных
    data = []

    # Обрабатываем каждую Feature из GeoJSON
    for feature in geojson_data["features"]:
        properties = feature.get("properties", {})
        geometry = feature.get("geometry", {})

        # Извлечение данных из properties
        name = properties.get("name", "Unnamed Zone")
        description = properties.get("description", "No description")

        # Проверка типа геометрии
        geom_type = geometry.get("type", "")
        coordinates = geometry.get("coordinates", [])

        # Преобразование геометрии для удобства работы
        try:
            geom = shape(geometry)
            centroid = geom.centroid
            centroid_lat, centroid_lon = centroid.y, centroid.x
        except Exception as e:
            print(f"Ошибка при обработке геометрии: {e}")
            continue

        # Добавляем данные в список
        data.append({
            "name": name,
            "description": description,
            "geometry_type": geom_type,
            "coordinates": coordinates,
            "centroid_lat": centroid_lat,
            "centroid_lon": centroid_lon
        })

    # Преобразуем данные в DataFrame
    df = pd.DataFrame(data)
    return df
