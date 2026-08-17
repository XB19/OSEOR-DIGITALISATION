from django.contrib import admin

from .models import JournalAction


@admin.register(JournalAction)
class JournalActionAdmin(admin.ModelAdmin):
    list_display = ("date_creation", "action", "acteur", "cible", "objet_type", "objet_id")
    list_filter = ("action", "objet_type", "date_creation")
    search_fields = ("action", "cible", "acteur__username")
    date_hierarchy = "date_creation"
    readonly_fields = (
        "acteur", "action", "cible", "objet_type", "objet_id", "details", "date_creation",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
