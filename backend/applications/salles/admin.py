from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Salle


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "filiale",
        "capacite",
        "active",
    )

    list_filter = (
        "filiale",
        "active",
    )

    search_fields = (
        "nom",
        "filiale__nom",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
    )