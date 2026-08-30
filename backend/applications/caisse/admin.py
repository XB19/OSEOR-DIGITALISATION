from django.contrib import admin

from .models import BonSortie, Caisse, MouvementCaisse


class MouvementInline(admin.TabularInline):
    model = MouvementCaisse
    extra = 0
    readonly_fields = ("type_mouvement", "montant", "motif", "cree_par",
                       "date_operation")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Caisse)
class CaisseAdmin(admin.ModelAdmin):
    list_display = ("nom", "code", "filiale", "detenteur", "solde", "active")
    search_fields = ("nom", "code")
    list_filter = ("filiale", "active")
    autocomplete_fields = ("detenteur",)
    inlines = [MouvementInline]

    @admin.display(description="Solde")
    def solde(self, obj):
        return obj.solde


@admin.register(MouvementCaisse)
class MouvementCaisseAdmin(admin.ModelAdmin):
    list_display = ("caisse", "type_mouvement", "montant", "motif",
                    "cree_par", "date_operation")
    search_fields = ("motif", "reference", "caisse__code")
    list_filter = ("type_mouvement", "caisse")
    date_hierarchy = "date_operation"
    autocomplete_fields = ("cree_par",)

    # Le registre fait foi : un ecart se corrige en ajoutant une ecriture.
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BonSortie)
class BonSortieAdmin(admin.ModelAdmin):
    list_display = ("reference", "objet", "montant", "type_depense",
                    "demandeur", "destinataire", "statut")
    search_fields = ("reference", "objet")
    list_filter = ("statut", "type_depense", "caisse")
    autocomplete_fields = ("demandeur", "destinataire")
