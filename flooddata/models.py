from django.contrib.gis.db import models
from django.contrib.auth.models import User

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