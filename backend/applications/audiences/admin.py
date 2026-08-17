from django.contrib import admin

from .models import Audience, EchangeAudience, Delegation


class EchangeAudienceInline(admin.TabularInline):
    model = EchangeAudience
    extra = 0
    readonly_fields = ("date_creation",)


class DelegationInline(admin.TabularInline):
    model = Delegation
    extra = 0
    readonly_fields = ("date_proposition", "date_prise_en_compte")


@admin.register(Audience)
class AudienceAdmin(admin.ModelAdmin):

    list_display = (
        "nom",
        "prenom",
        "dg",
        "statut",
        "date_souhaitee",
        "secretaire",
    )

    list_filter = (
        "statut",
        "dg",
        "date_souhaitee",
    )

    search_fields = (
        "nom",
        "prenom",
        "profession",
        "objet_visite",
    )

    date_hierarchy = "date_creation"

    readonly_fields = (
        "date_creation",
        "date_modification",
        "date_confirmation",
    )

    inlines = [EchangeAudienceInline, DelegationInline]


@admin.register(Delegation)
class DelegationAdmin(admin.ModelAdmin):

    list_display = (
        "audience",
        "delegue",
        "statut",
        "date_proposition",
        "date_prise_en_compte",
    )

    list_filter = ("statut",)

    search_fields = (
        "delegue__first_name",
        "delegue__last_name",
        "delegue__email",
    )
