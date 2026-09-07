from django.contrib import admin

from .models import Visite


@admin.register(Visite)
class VisiteAdmin(admin.ModelAdmin):

    list_display = ("nom", "prenom", "numero_piece", "filiale", "heure_arrivee", "heure_depart")
    list_filter = ("filiale", "heure_arrivee")
    search_fields = ("nom", "prenom", "numero_piece")
    readonly_fields = ("heure_arrivee",)
