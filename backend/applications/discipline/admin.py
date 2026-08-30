from django.contrib import admin

from .models import ExplicationSalarie, ProcedureDisciplinaire, Sanction


class ExplicationInline(admin.TabularInline):
    model = ExplicationSalarie
    extra = 0
    readonly_fields = ("mode", "contenu", "delegue_present", "consignee_par",
                       "date_explication")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ProcedureDisciplinaire)
class ProcedureDisciplinaireAdmin(admin.ModelAdmin):
    list_display = ("reference", "salarie", "qualification", "statut",
                    "date_preuve", "date_limite_sanction", "delai_depasse")
    search_fields = ("reference", "salarie__last_name", "salarie__username")
    list_filter = ("statut", "qualification", "filiale")
    date_hierarchy = "date_faits"
    autocomplete_fields = ("salarie", "ouverte_par")
    inlines = [ExplicationInline]

    @admin.display(description="Delai limite")
    def date_limite_sanction(self, obj):
        return obj.date_limite_sanction

    @admin.display(boolean=True, description="Delai depasse")
    def delai_depasse(self, obj):
        return obj.delai_depasse


@admin.register(Sanction)
class SanctionAdmin(admin.ModelAdmin):
    list_display = ("procedure", "type_sanction", "duree_jours",
                    "prononcee_par", "date_prononce", "formalites_completes")
    search_fields = ("procedure__reference",)
    list_filter = ("type_sanction",)
    date_hierarchy = "date_prononce"
    autocomplete_fields = ("prononcee_par",)

    # Une sanction prononcee ne se retouche pas : elle se conteste.
    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(boolean=True, description="Formalites completes")
    def formalites_completes(self, obj):
        return obj.formalites_completes
