import os
from celery import Celery

# Установка переменной окружения для настроек проекта
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'floodportal.settings')

app = Celery('floodportal')

# Использовать настройки Django для Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение задач в приложениях
app.autodiscover_tasks()

# Настройка периодических задач
app.conf.beat_schedule = {
    'update-water-levels-every-hour': {
        'task': 'flooddata.tasks.update_water_level_data',
        'schedule': 3600.0,  # каждый час
    },
    'cleanup-old-forecasts-daily': {
        'task': 'flooddata.tasks.cleanup_old_forecast_data',
        'schedule': 86400.0,  # каждый день
    },
    'detect-flood-events-every-6-hours': {
        'task': 'flooddata.tasks.detect_flood_events',
        'schedule': 21600.0,  # каждые 6 часов
    },
} 