from django.contrib import admin

from .models import Reservation, Participant


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):

    list_display = (
        "nom_reservant",
        "salle",
        "date_reunion",
        "heure_debut",
        "heure_fin",
        "statut",
        "demandeur",
    )

    list_filter = (
        "statut",
        "date_reunion",
        "salle__filiale",
        "salle",
    )

    search_fields = (
        "nom_reservant",
        "demandeur__first_name",
        "demandeur__last_name",
        "demandeur__username",
        "salle__nom",
    )

    readonly_fields = (
        "date_creation",
        "date_modification",
        "date_validation",
        "date_annulation",
    )

    date_hierarchy = "date_reunion"

    ordering = (
        "-date_reunion",
        "-heure_debut",
    )

    inlines = [ParticipantInline]

    fieldsets = (
        (
            "Informations générales",
            {
                "fields": (
                    "demandeur",
                    "nom_reservant",
                    "salle",
                )
            },
        ),
        (
            "Planification",
            {
                "fields": (
                    "date_reunion",
                    "heure_debut",
                    "heure_fin",
                )
            },
        ),
        (
            "Détails",
            {
                "fields": (
                    "precisions",
                )
            },
        ),
        (
            "Validation",
            {
                "fields": (
                    "statut",
                    "motif_refus",
                    "valide_par",
                    "date_validation",
                )
            },
        ),
        (
            "Annulation",
            {
                "fields": (
                    "annule_par",
                    "date_annulation",
                    "motif_annulation",
                )
            },
        ),
        (
            "Historique",
            {
                "fields": (
                    "date_creation",
                    "date_modification",
                )
            },
        ),
    )


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):

    list_display = (
        "nom_complet",
        "email",
        "reservation",
    )

    search_fields = (
        "nom_complet",
        "email",
    )

    ordering = (
        "nom_complet",
    )