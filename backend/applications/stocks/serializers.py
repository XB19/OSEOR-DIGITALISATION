from rest_framework import serializers

from .models import Article, MouvementStock


class ArticleSerializer(serializers.ModelSerializer):
    categorie_libelle = serializers.CharField(source="get_categorie_display", read_only=True)
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)
    en_alerte = serializers.BooleanField(read_only=True)

    class Meta:
        model = Article
        fields = (
            "id", "nom", "categorie", "categorie_libelle", "unite",
            "quantite_stock", "seuil_alerte", "description", "actif",
            "filiale", "filiale_nom", "en_alerte",
            "date_creation", "date_modification",
        )
        read_only_fields = ("filiale", "quantite_stock", "date_creation", "date_modification")

    def create(self, validated_data):
        # L'article appartient toujours à la filiale de celui qui le crée.
        validated_data["filiale"] = self.context["request"].user.filiale
        return super().create(validated_data)


class MouvementStockSerializer(serializers.ModelSerializer):
    """
    Enregistre un mouvement ET met à jour `quantite_stock` de l'article —
    jamais l'inverse : le stock affiché est toujours dérivé du registre des
    mouvements, jamais une valeur libre modifiable directement.
    """

    article_nom = serializers.CharField(source="article.nom", read_only=True)
    type_mouvement_libelle = serializers.CharField(source="get_type_mouvement_display", read_only=True)
    utilisateur_nom = serializers.CharField(source="utilisateur.nom_complet", read_only=True)

    class Meta:
        model = MouvementStock
        fields = (
            "id", "article", "article_nom", "type_mouvement", "type_mouvement_libelle",
            "quantite", "motif", "utilisateur", "utilisateur_nom", "date_creation",
        )
        read_only_fields = ("utilisateur", "date_creation")

    def validate(self, attrs):
        article = attrs["article"]
        if attrs["type_mouvement"] == MouvementStock.Type.SORTIE and attrs["quantite"] > article.quantite_stock:
            raise serializers.ValidationError(
                f"Stock insuffisant : {article.quantite_stock} {article.unite}(s) disponible(s) pour « {article.nom} »."
            )
        return attrs

    def create(self, validated_data):
        from django.db.models import F

        validated_data["utilisateur"] = self.context["request"].user
        mouvement = super().create(validated_data)

        article = mouvement.article
        delta = mouvement.quantite if mouvement.type_mouvement == MouvementStock.Type.ENTREE else -mouvement.quantite
        Article.objects.filter(pk=article.pk).update(quantite_stock=F("quantite_stock") + delta)
        article.refresh_from_db(fields=["quantite_stock"])

        mouvement._article_a_jour = article  # évite un 2e aller-retour BDD dans la vue
        return mouvement
