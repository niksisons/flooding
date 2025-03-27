from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import FloodEvent, FloodZone
from .tasks import update_geoserver_layers

@receiver(post_save, sender=FloodEvent)
@receiver(post_save, sender=FloodZone)
def update_geoserver_on_save(sender, instance, created, **kwargs):
    """Обновление слоев GeoServer при сохранении моделей"""
    update_geoserver_layers.delay()

@receiver(post_delete, sender=FloodEvent)
@receiver(post_delete, sender=FloodZone)
def update_geoserver_on_delete(sender, instance, **kwargs):
    """Обновление слоев GeoServer при удалении моделей"""
    update_geoserver_layers.delay() 