import os
import sys

print("Проверка переменных окружения:")
print(f"PATH: {os.environ.get('PATH', '')}")
print(f"GDAL_DATA: {os.environ.get('GDAL_DATA', '')}")
print(f"PROJ_LIB: {os.environ.get('PROJ_LIB', '')}")

try:
    from osgeo import gdal, ogr, osr
    print("\nGDAL успешно импортирован!")
    print(f"Версия GDAL: {gdal.VersionInfo('RELEASE_NAME')}")
except ImportError as e:
    print(f"\nОшибка импорта GDAL: {e}")
    print("Пути поиска Python модулей:")
    for path in sys.path:
        print(f"  - {path}")
    
try:
    from django.contrib.gis.gdal import gdal
    print("\nDjango GDAL успешно импортирован!")
except ImportError as e:
    print(f"\nОшибка импорта Django GDAL: {e}")

try:
    from django.contrib.gis.geos import GEOSGeometry
    print("\nDjango GEOS успешно импортирован!")
except ImportError as e:
    print(f"\nОшибка импорта Django GEOS: {e}") 