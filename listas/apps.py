from django.apps import AppConfig


class ListasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'listas'
    verbose_name = 'Listas de Canais'

    def ready(self):
        import listas.signals  # noqa: F401
