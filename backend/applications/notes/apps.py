from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'applications.notes'
    verbose_name = "Notes internes"

    def ready(self):
        # Branche la diffusion automatique d'une note une fois signée.
        from . import signals  # noqa: F401
