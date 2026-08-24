from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import GereLesStocks
from applications.journalisation.services import enregistrer_action
from .models import Article, MouvementStock
from .serializers import ArticleSerializer, MouvementStockSerializer
from .services import notifier_seuil_alerte


class ArticleViewSet(viewsets.ModelViewSet):
    """Catalogue des articles en stock (matériel, informatique, fournitures…)."""

    serializer_class = ArticleSerializer
    filterset_fields = ("categorie", "actif", "filiale")
    search_fields = ("nom", "description")
    ordering_fields = ("nom", "quantite_stock")
    permission_classes = [GereLesStocks]

    def get_queryset(self):
        qs = Article.objects.select_related("filiale")
        u = self.request.user
        if u.role in ("ADMINISTRATEUR", "DIRECTEUR"):
            return qs
        return qs.filter(filiale=u.filiale)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        article = serializer.save()
        enregistrer_action(self.request.user, "ARTICLE_CREE", article.nom, objet=article)

    def perform_update(self, serializer):
        article = serializer.save()
        enregistrer_action(self.request.user, "ARTICLE_MODIFIE", article.nom, objet=article)

    @action(detail=False, methods=["get"])
    def alertes(self, request):
        """Articles actifs dont le stock est à/sous leur seuil d'alerte."""
        qs = self.get_queryset().filter(actif=True)
        en_alerte = [a for a in qs if a.en_alerte]
        return Response(ArticleSerializer(en_alerte, many=True, context=self.get_serializer_context()).data)


class MouvementStockViewSet(viewsets.ModelViewSet):
    """Registre des entrées/sorties de stock — append-only (jamais modifié ni supprimé)."""

    http_method_names = ["get", "post", "head", "options"]
    serializer_class = MouvementStockSerializer
    filterset_fields = ("article", "type_mouvement")
    ordering_fields = ("date_creation",)
    permission_classes = [GereLesStocks]

    def get_queryset(self):
        qs = MouvementStock.objects.select_related("article", "article__filiale", "utilisateur")
        u = self.request.user
        if u.role in ("ADMINISTRATEUR", "DIRECTEUR"):
            return qs
        return qs.filter(article__filiale=u.filiale)

    def get_serializer_context(self):
        return {"request": self.request}

    def perform_create(self, serializer):
        mouvement = serializer.save()
        enregistrer_action(
            self.request.user, "MOUVEMENT_STOCK",
            f"{mouvement.get_type_mouvement_display()} {mouvement.quantite} {mouvement.article.unite} — {mouvement.article.nom}",
            objet=mouvement,
        )

        article = getattr(mouvement, "_article_a_jour", mouvement.article)
        if mouvement.type_mouvement == MouvementStock.Type.SORTIE and article.en_alerte:
            notifier_seuil_alerte(article)
