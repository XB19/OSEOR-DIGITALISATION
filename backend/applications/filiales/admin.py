from django.contrib import admin
from .models import Filiale, ParametreFiliale, Service


@admin.register(Filiale)
class FilialeAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "code",
        "email",
        "telephone",
        "active",
    )

    search_fields = (
        "nom",
        "code",
        "email",
    )

    list_filter = (
        "active",
    )


@admin.register(ParametreFiliale)
class ParametreFilialeAdmin(admin.ModelAdmin):

    list_display = (
        "filiale",
        "delai_min_reservation",
        "duree_max_reservation",
        "nb_max_reservations_actives",
        "delai_annulation",
    )

    search_fields = (
        "filiale__nom",
    )

    list_filter = (
        "filiale",
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "code",
        "filiale",
        "chef",
        "actif",
    )

    search_fields = (
        "nom",
        "code",
        "filiale__nom",
    )

    list_filter = (
        "filiale",
        "actif",
    )

    autocomplete_fields = (
        "chef",
    )
