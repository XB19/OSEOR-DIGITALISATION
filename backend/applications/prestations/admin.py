from django.contrib import admin

from .models import JalonPrestation, Prestation


class JalonInline(admin.TabularInline):
    model = JalonPrestation
    extra = 0


@admin.register(Prestation)
class PrestationAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "intitule", "client", "service", "statut",
        "date_debut", "date_fin_prevue",
    )
    search_fields = ("reference", "intitule", "client")
    list_filter = ("statut", "filiale", "service")
    date_hierarchy = "date_debut"
    autocomplete_fields = ("responsable", "service")
    inlines = [JalonInline]


@admin.register(JalonPrestation)
class JalonPrestationAdmin(admin.ModelAdmin):
    list_display = ("prestation", "intitule", "date_prevue", "date_realisation")
    search_fields = ("intitule", "prestation__reference")
    list_filter = ("date_realisation",)
