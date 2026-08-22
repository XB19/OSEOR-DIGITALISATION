from django.contrib import admin

from .models import LectureNote


@admin.register(LectureNote)
class LectureNoteAdmin(admin.ModelAdmin):

    list_display = (
        "note",
        "destinataire",
        "date_diffusion",
        "date_lecture",
    )

    search_fields = (
        "note__numero",
        "destinataire__username",
        "destinataire__last_name",
    )

    list_filter = (
        "date_lecture",
        "note__filiale",
    )

    autocomplete_fields = (
        "destinataire",
    )
