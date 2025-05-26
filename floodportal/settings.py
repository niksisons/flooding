import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-your-secret-key-here1234567890abcdef'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*']

# Отображение подробных ошибок
ADMINS = [
    ('Admin', 'admin@example.com'),
]
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
SERVER_EMAIL = 'root@localhost'

# Конфигурация логирования для отладки
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

# GDAL settings
if os.name == 'nt':
    os.environ['PATH'] = r'C:\OSGeo4W\bin;' + os.environ['PATH']
    os.environ['GDAL_DATA'] = r'C:\OSGeo4W\share\gdal'
    os.environ['PROJ_LIB'] = r'C:\OSGeo4W\share\proj'
    
    # Явно указываем путь к DLL файлам для версии 3.10
    from ctypes import WinDLL
    import sys
    
    try:
        # Пытаемся загрузить GDAL DLL напрямую
        gdal_dll_path = r'C:\OSGeo4W\bin\gdal310.dll'
        geos_dll_path = r'C:\OSGeo4W\bin\geos_c.dll'
        if os.path.exists(gdal_dll_path):
            gdal_module = WinDLL(gdal_dll_path)
            GDAL_LIBRARY_PATH = gdal_dll_path
        else:
            # Ищем все возможные dll файлы GDAL в папке bin
            gdal_bin_path = r'C:\OSGeo4W\bin'
            gdal_dll_files = [f for f in os.listdir(gdal_bin_path) if f.startswith('gdal') and f.endswith('.dll')]
            if gdal_dll_files:
                GDAL_LIBRARY_PATH = os.path.join(gdal_bin_path, gdal_dll_files[0])
        
        if os.path.exists(geos_dll_path):
            GEOS_LIBRARY_PATH = geos_dll_path
    except Exception as e:
        print(f"Ошибка при загрузке библиотек GDAL: {e}")
        
    # Добавляем другие настройки
    GDAL_LIBRARY_PATH = r'C:\OSGeo4W\bin\gdal310.dll'
    GEOS_LIBRARY_PATH = r'C:\OSGeo4W\bin\geos_c.dll'
    
# Если OS не Windows, то не устанавливаем эти параметры

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',  # GeoDjango
    'rest_framework',
    'rest_framework_gis',  # Для работы с геоданными в DRF
    'rest_framework.authtoken',  # Для токен-аутентификации
    'django_celery_beat',  # Для планирования задач Celery
    'corsheaders',  # Для CORS
    'flooddata',  # Наше приложение для работы с данными о затоплениях
    'background_task',  # Для фоновых задач
]

# Настройка TEMPLATES
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Полный список MIDDLEWARE
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Настройка базы данных с PostGIS
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'floodportal',
        'USER': 'postgres',
        'PASSWORD': '1q9i2w8u3e7y4r6t',  # ваш пароль
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Добавьте после определения DATABASES
SPATIALITE_LIBRARY_PATH = r'C:\OSGeo4W\bin\mod_spatialite.dll'

# Настройки REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Настройки кэша (если нужен Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# CORS настройки
CORS_ALLOW_ALL_ORIGINS = True  # В продакшене лучше указать конкретные домены 

# Настройки статических файлов
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_collected')  # Папка для collectstatic
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Папка для собственных статических файлов
]
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

ROOT_URLCONF = 'floodportal.urls'