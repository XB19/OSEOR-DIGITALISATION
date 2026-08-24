from django.contrib import admin

from .models import DemandeConge, JourFerie, MouvementConge


@admin.register(JourFerie)
class JourFerieAdmin(admin.ModelAdmin):
    list_display = ("date", "nom", "filiale")
    search_fields = ("nom",)
    list_filter = ("filiale",)
    date_hierarchy = "date"


@admin.register(DemandeConge)
class DemandeCongeAdmin(admin.ModelAdmin):
    list_display = (
        "utilisateur", "type_conge", "date_debut", "date_fin",
        "jours_ouvres", "statut",
    )
    search_fields = ("utilisateur__username", "utilisateur__last_name")
    list_filter = ("statut", "type_conge")
    date_hierarchy = "date_debut"
    autocomplete_fields = ("utilisateur", "valideur")


@admin.register(MouvementConge)
class MouvementCongeAdmin(admin.ModelAdmin):
    list_display = (
        "utilisateur", "annee", "type_mouvement", "jours", "date_effet",
    )
    search_fields = ("utilisateur__username", "utilisateur__last_name")
    list_filter = ("annee", "type_mouvement")
    date_hierarchy = "date_effet"
    autocomplete_fields = ("utilisateur",)

    # Le registre est la source de vérité du solde : une correction s'écrit
    # en ajoutant une ecriture inverse, jamais en retouchant l'historique.
    def has_change_permission(self, request, obj=None):
        return False
