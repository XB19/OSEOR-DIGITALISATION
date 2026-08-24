from django.contrib import admin

from .models import Contrat, PieceJointeContrat


class PieceJointeContratInline(admin.TabularInline):
    model = PieceJointeContrat
    extra = 0
    readonly_fields = ("ajoute_par", "date_ajout")


@admin.register(Contrat)
class ContratAdmin(admin.ModelAdmin):

    list_display = ("numero", "intitule", "partie_contractante", "type_contrat", "filiale", "statut", "date_echeance")
    list_filter = ("type_contrat", "statut", "filiale")
    search_fields = ("numero", "intitule", "partie_contractante", "reference")
    readonly_fields = ("numero", "seuils_alertes_envoyes", "date_creation", "date_modification")
    inlines = [PieceJointeContratInline]
