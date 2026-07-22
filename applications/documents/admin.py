from django.contrib import admin

from .models import ConfigurationDocument, Document


@admin.register(ConfigurationDocument)
class ConfigurationDocumentAdmin(admin.ModelAdmin):

    list_display = ("filiale", "type_document")
    list_filter = ("type_document", "filiale")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "numero", "type_document", "filiale", "demandeur", "statut", "date_creation",
    )

    list_filter = ("type_document", "statut", "filiale")
    search_fields = ("numero",)
    readonly_fields = (
        "numero", "filiale", "type_document", "demandeur",
        "date_creation", "date_modification",
    )
