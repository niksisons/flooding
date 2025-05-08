from django.contrib.gis.db import models
from django.contrib.auth.models import User
import os

# Функция для сброса и создания базы данных заново
def reset_db():
    """
    Сбрасывает и создает базу данных заново.
    Используйте эту функцию только для разработки!
    """
    from django.db import connection
    cursor = connection.cursor()
    
    # Удаляем все таблицы flooddata
    tables = [
        'flooddata_floodzone',
        'flooddata_floodevent',
        'flooddata_measurementpoint',
        'flooddata_waterlevelmeasurement',
        'flooddata_demfile',
        'flooddata_satelliteimage',
        'flooddata_floodanalysis'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        except Exception as e:
            print(f"Ошибка при удалении {table}: {e}")
    
    # Удаляем записи миграций для flooddata
    cursor.execute("DELETE FROM django_migrations WHERE app = 'flooddata'")
    connection.commit()
    
    print("База данных сброшена. Теперь выполните makemigrations и migrate.")

class FloodZone(models.Model):
    """Модель для зон затопления"""
    name = models.CharField(max_length=255, verbose_name="Название")
    description = models.TextField(verbose_name="Описание", blank=True)
    geometry = models.PolygonField(srid=4326, verbose_name="Геометрия")
    risk_level = models.PositiveSmallIntegerField(
        verbose_name="Уровень риска",
        choices=(
            (1, "Низкий"),
            (2, "Средний"),
            (3, "Высокий"),
        ),
        default=1
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                  related_name="created_zones", verbose_name="Создано")
    
    class Meta:
        verbose_name = "Зона затопления"
        verbose_name_plural = "Зоны затопления"
    
    def __str__(self):
        return self.name

class FloodEvent(models.Model):
    """Модель для событий затопления"""
    title = models.CharField(max_length=255, verbose_name="Название события")
    description = models.TextField(verbose_name="Описание", blank=True)
    geometry = models.MultiPolygonField(srid=4326, verbose_name="Область затопления")
    event_start = models.DateTimeField(verbose_name="Начало события")
    event_end = models.DateTimeField(verbose_name="Окончание события", null=True, blank=True)
    water_level = models.DecimalField(max_digits=5, decimal_places=2, 
                                     verbose_name="Уровень воды (м)", null=True, blank=True)
    source = models.CharField(max_length=255, verbose_name="Источник данных", blank=True)
    is_forecast = models.BooleanField(default=False, verbose_name="Прогноз")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, 
                                   related_name="created_events", verbose_name="Создано")
    
    class Meta:
        verbose_name = "Событие затопления"
        verbose_name_plural = "События затопления"
        indexes = [
            models.Index(fields=['event_start', 'event_end']),
            models.Index(fields=['is_forecast']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.event_start.strftime('%d.%m.%Y')})"

class MeasurementPoint(models.Model):
    """Модель для точек измерения уровня воды"""
    name = models.CharField(max_length=255, verbose_name="Название")
    code = models.CharField(max_length=50, verbose_name="Код/Идентификатор", blank=True)
    location = models.PointField(srid=4326, verbose_name="Местоположение")
    description = models.TextField(verbose_name="Описание", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Точка измерения"
        verbose_name_plural = "Точки измерения"
    
    def __str__(self):
        return self.name

class WaterLevelMeasurement(models.Model):
    """Модель для измерений уровня воды"""
    point = models.ForeignKey(MeasurementPoint, on_delete=models.CASCADE, 
                             related_name="measurements", verbose_name="Точка измерения")
    timestamp = models.DateTimeField(verbose_name="Время измерения")
    value = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Значение (м)")
    is_forecast = models.BooleanField(default=False, verbose_name="Прогноз")
    
    class Meta:
        verbose_name = "Измерение уровня воды"
        verbose_name_plural = "Измерения уровня воды"
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_forecast']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.point.name}: {self.value}м ({self.timestamp.strftime('%d.%m.%Y %H:%M')})"

class DEMFile(models.Model):
    """Модель для файлов цифровой модели рельефа"""
    name = models.CharField(max_length=255, default="Цифровая модель рельефа", verbose_name="Название")
    file = models.FileField(upload_to='dem_files/', verbose_name="DEM файл")
    description = models.TextField(blank=True, verbose_name="Описание")
    upload_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                   related_name="dem_files", verbose_name="Загружено")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_base_layer = models.BooleanField(default=False, verbose_name="Базовый слой")
    
    class Meta:
        verbose_name = "DEM файл"
        verbose_name_plural = "DEM файлы"
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.name} ({self.upload_date.strftime('%d.%m.%Y')})"

class SatelliteImage(models.Model):
    """Модель для космических снимков"""
    name = models.CharField(max_length=255, default="Космический снимок", verbose_name="Название")
    file = models.FileField(upload_to='satellite_images/', verbose_name="Космический снимок")
    description = models.TextField(blank=True, verbose_name="Описание")
    upload_date = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    image_date = models.DateField(verbose_name="Дата снимка")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                   related_name="satellite_images", verbose_name="Загружено")
    status = models.CharField(
        max_length=50,
        choices=(
            ('new', 'Новый'),
            ('processing', 'В обработке'),
            ('completed', 'Обработан'),
            ('error', 'Ошибка'),
        ),
        default='new',
        verbose_name="Статус"
    )
    area = models.PolygonField(srid=4326, null=True, blank=True, verbose_name="Область снимка")
    
    class Meta:
        verbose_name = "Космический снимок"
        verbose_name_plural = "Космические снимки"
        ordering = ['-upload_date']
    
    def __str__(self):
        return f"{self.name} ({self.image_date.strftime('%d.%m.%Y')})"

class FloodAnalysis(models.Model):
    """Модель для анализа затопления"""
    name = models.CharField(max_length=255, default="Анализ затопления", verbose_name="Название анализа")
    dem_file = models.ForeignKey(DEMFile, on_delete=models.CASCADE, 
                                related_name="analyses", verbose_name="DEM файл")
    satellite_image = models.ForeignKey(SatelliteImage, on_delete=models.CASCADE, 
                                       related_name="analyses", verbose_name="Космический снимок")
    flood_mask = models.FileField(upload_to='analysis_results/', null=True, blank=True, 
                                 verbose_name="Маска затопления")
    flood_vector = models.MultiPolygonField(srid=4326, null=True, blank=True, 
                                          verbose_name="Векторный слой затопления")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  related_name="analyses", verbose_name="Создано")
    status = models.CharField(
        max_length=50,
        choices=(
            ('pending', 'В очереди'),
            ('processing', 'В обработке'),
            ('completed', 'Завершено'),
            ('error', 'Ошибка'),
        ),
        default='pending',
        verbose_name="Статус"
    )
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    flooded_area_sqkm = models.FloatField(null=True, blank=True, verbose_name="Площадь затопления (кв.км)")
    compared_with_base = models.BooleanField(default=False, verbose_name="Сравнено с базовым слоем")
    
    class Meta:
        verbose_name = "Анализ затопления"
        verbose_name_plural = "Анализы затоплений"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.created_at.strftime('%d.%m.%Y %H:%M')})"