from django.contrib import admin

from .models import Album, Photo


class PhotoInline(admin.TabularInline):
    model = Photo
    extra = 0
    readonly_fields = ("miniature", "largeur", "hauteur", "taille_octets")


@admin.register(Album)
class AlbumAdmin(admin.ModelAdmin):
    list_display = (
        "titre", "filiale", "evenement", "visibilite", "date_evenement",
    )
    search_fields = ("titre", "description")
    list_filter = ("visibilite", "filiale")
    autocomplete_fields = ("createur", "service")
    inlines = [PhotoInline]


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("album", "legende", "televersee_par", "date_creation")
    search_fields = ("legende", "album__titre")
    list_filter = ("album__filiale",)
    readonly_fields = ("miniature", "largeur", "hauteur", "taille_octets")
    autocomplete_fields = ("televersee_par",)
