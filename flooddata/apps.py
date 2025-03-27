from django.apps import AppConfig

class FlooddataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'flooddata'
    verbose_name = 'Данные о затоплениях'

    def ready(self):
        """Импорт сигналов при запуске приложения"""
        import flooddata.signals 