# Сигналы для FloodEvent и FloodZone больше не обновляют GeoServer через Celery.
# Если потребуется — реализуйте обновление через обычную функцию или django-background-tasks.

# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from .models import FloodEvent, FloodZone

# @receiver(post_save, sender=FloodEvent)
# @receiver(post_save, sender=FloodZone)
# def update_geoserver_on_save(sender, instance, created, **kwargs):
#     pass

# @receiver(post_delete, sender=FloodEvent)
# @receiver(post_delete, sender=FloodZone)
# def update_geoserver_on_delete(sender, instance, **kwargs):
#     pass