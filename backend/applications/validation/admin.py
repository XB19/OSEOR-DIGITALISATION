from django.contrib import admin

from .models import DecisionValidation


@admin.register(DecisionValidation)
class DecisionValidationAdmin(admin.ModelAdmin):
    list_display = (
        "objet_type", "objet_id", "etape_libelle", "acteur", "sens",
        "validation_directe", "date_decision",
    )
    search_fields = ("objet_type", "etape_libelle", "acteur__username")
    list_filter = ("sens", "validation_directe", "objet_type")
    date_hierarchy = "date_decision"
    autocomplete_fields = ("acteur",)

    # Le circuit est une piste d'audit : une décision se corrige en en
    # ajoutant une autre, jamais en retouchant celle-ci.
    def has_change_permission(self, request, obj=None):
        return False
