from django.contrib import admin

from .models import EntreeAide


@admin.register(EntreeAide)
class EntreeAideAdmin(admin.ModelAdmin):

    list_display = ("question", "module", "ordre", "actif")
    list_filter = ("module", "actif")
    search_fields = ("question", "mots_cles")
    list_editable = ("ordre", "actif")
