from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur, ParametreLDAP


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):

    list_display = (
        "username",
        "first_name",
        "last_name",
        "role",
        "filiale",
        "is_active",
    )

    list_filter = (
        "role",
        "filiale",
        "is_active",
    )

    fieldsets = UserAdmin.fieldsets + (
        (
            "Informations OSEOR",
            {
                "fields": (
                    "role",
                    "filiale",
                    "telephone",
                    "photo_profil",
                    "signature",
                )
            },
        ),
    )


@admin.register(ParametreLDAP)
class ParametreLDAPAdmin(admin.ModelAdmin):

    list_display = (
        "server_uri",
        "domaine",
        "base_dn",
        "date_modification",
    )

    readonly_fields = ("date_modification",)