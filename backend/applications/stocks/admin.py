from django.contrib import admin

from .models import Article, MouvementStock


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):

    list_display = ("nom", "categorie", "filiale", "quantite_stock", "seuil_alerte", "actif")
    list_filter = ("categorie", "filiale", "actif")
    search_fields = ("nom", "description")
    readonly_fields = ("quantite_stock",)


@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):

    list_display = ("article", "type_mouvement", "quantite", "utilisateur", "date_creation")
    list_filter = ("type_mouvement", "article__filiale")
    search_fields = ("article__nom", "motif")
    readonly_fields = ("date_creation",)
