import requests
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Настройки подключения к GeoServer
GEOSERVER_URL = getattr(settings, 'GEOSERVER_URL', 'http://localhost:8080/geoserver')
GEOSERVER_USER = getattr(settings, 'GEOSERVER_USER', 'admin')
GEOSERVER_PASSWORD = getattr(settings, 'GEOSERVER_PASSWORD', 'geoserver')
GEOSERVER_WORKSPACE = getattr(settings, 'GEOSERVER_WORKSPACE', 'floodportal')

def create_workspace_if_not_exists():
    """Создание рабочего пространства в GeoServer"""
    url = f"{GEOSERVER_URL}/rest/workspaces/{GEOSERVER_WORKSPACE}"
    
    # Проверяем, существует ли рабочее пространство
    response = requests.get(
        url,
        auth=(GEOSERVER_USER, GEOSERVER_PASSWORD),
        headers={'Accept': 'application/json'}
    )
    
    if response.status_code == 200:
        logger.info(f"Рабочее пространство {GEOSERVER_WORKSPACE} уже существует")
        return True
    
    # Создаем новое рабочее пространство
    create_url = f"{GEOSERVER_URL}/rest/workspaces"
    data = {
        "workspace": {
            "name": GEOSERVER_WORKSPACE
        }
    }
    
    response = requests.post(
        create_url,
        auth=(GEOSERVER_USER, GEOSERVER_PASSWORD),
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data)
    )
    
    if response.status_code == 201:
        logger.info(f"Рабочее пространство {GEOSERVER_WORKSPACE} успешно создано")
        return True
    else:
        logger.error(f"Ошибка при создании рабочего пространства: {response.text}")
        return False

def create_postgis_store():
    """Создание хранилища данных PostGIS в GeoServer"""
    url = f"{GEOSERVER_URL}/rest/workspaces/{GEOSERVER_WORKSPACE}/datastores/floodportal_data"
    
    # Проверяем, существует ли хранилище
    response = requests.get(
        url,
        auth=(GEOSERVER_USER, GEOSERVER_PASSWORD),
        headers={'Accept': 'application/json'}
    )
    
    if response.status_code == 200:
        logger.info("Хранилище PostGIS уже существует")
        return True
    
    # Создаем новое хранилище PostGIS
    data = {
        "dataStore": {
            "name": "floodportal_data",
            "connectionParameters": {
                "entry": [
                    {"@key": "host", "$": settings.DATABASES['default']['HOST']},
                    {"@key": "port", "$": settings.DATABASES['default']['PORT']},
                    {"@key": "database", "$": settings.DATABASES['default']['NAME']},
                    {"@key": "user", "$": settings.DATABASES['default']['USER']},
                    {"@key": "passwd", "$": settings.DATABASES['default']['PASSWORD']},
                    {"@key": "dbtype", "$": "postgis"},
                    {"@key": "schema", "$": "public"}
                ]
            }
        }
    }
    
    response = requests.post(
        f"{GEOSERVER_URL}/rest/workspaces/{GEOSERVER_WORKSPACE}/datastores",
        auth=(GEOSERVER_USER, GEOSERVER_PASSWORD),
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data)
    )
    
    if response.status_code == 201:
        logger.info("Хранилище PostGIS успешно создано")
        return True
    else:
        logger.error(f"Ошибка при создании хранилища: {response.text}")
        return False

def publish_layer(table_name, layer_name, title, abstract=None):
    """Публикация слоя из PostGIS в GeoServer"""
    url = f"{GEOSERVER_URL}/rest/workspaces/{GEOSERVER_WORKSPACE}/datastores/floodportal_data/featuretypes"
    
    data = {
        "featureType": {
            "name": layer_name,
            "nativeName": table_name,
            "title": title,
            "abstract": abstract or title,
            "enabled": True,
            "srs": "EPSG:4326"
        }
    }
    
    response = requests.post(
        url,
        auth=(GEOSERVER_USER, GEOSERVER_PASSWORD),
        headers={'Content-Type': 'application/json'},
        data=json.dumps(data)
    )
    
    if response.status_code == 201:
        logger.info(f"Слой {layer_name} успешно опубликован")
        return True
    else:
        logger.error(f"Ошибка при публикации слоя {layer_name}: {response.text}")
        return False

def setup_geoserver():
    """Настройка GeoServer для работы с данными проекта"""
    if not create_workspace_if_not_exists():
        return False
    
    if not create_postgis_store():
        return False
    
    # Публикуем основные слои
    layers_to_publish = [
        {
            "table": "flooddata_floodzone",
            "name": "flood_zones",
            "title": "Зоны затопления",
            "abstract": "Зоны с риском затопления"
        },
        {
            "table": "flooddata_floodevent",
            "name": "flood_events",
            "title": "События затопления",
            "abstract": "Исторические и прогнозируемые события затопления"
        },
        {
            "table": "flooddata_measurementpoint",
            "name": "measurement_points",
            "title": "Точки измерения",
            "abstract": "Точки измерения уровня воды"
        }
    ]
    
    for layer in layers_to_publish:
        publish_layer(
            layer["table"], 
            layer["name"], 
            layer["title"], 
            layer["abstract"]
        )
    
    return True