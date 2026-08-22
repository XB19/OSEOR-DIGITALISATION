from django.contrib import admin

from .models import Evenement


@admin.register(Evenement)
class EvenementAdmin(admin.ModelAdmin):

    list_display = (
        "titre",
        "type_evenement",
        "date_debut",
        "filiale",
        "visibilite",
        "annule",
    )

    search_fields = (
        "titre",
        "description",
        "lieu",
    )

    list_filter = (
        "type_evenement",
        "visibilite",
        "filiale",
        "annule",
    )

    date_hierarchy = "date_debut"

    autocomplete_fields = (
        "createur",
        "service",
    )
