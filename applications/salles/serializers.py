from rest_framework import serializers

from .models import Salle


class SalleSerializer(serializers.ModelSerializer):
    filiale_nom = serializers.CharField(source="filiale.nom", read_only=True)

    class Meta:
        model = Salle
        fields = (
            "id",
            "nom",
            "filiale",
            "filiale_nom",
            "description",
            "capacite",
            "equipements",
            "photo",
            "active",
        )

    def validate_equipements(self, value):
        if value in (None, ""):
            return []
        # En multipart (upload photo), la liste arrive en chaîne JSON.
        if isinstance(value, str):
            import json
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                raise serializers.ValidationError(
                    "Format des équipements invalide."
                )
        if not isinstance(value, list):
            raise serializers.ValidationError(
                "Les équipements doivent être une liste de codes."
            )
        valides = {c for c, _ in Salle.Equipement.choices}
        inconnus = [v for v in value if v not in valides]
        if inconnus:
            raise serializers.ValidationError(
                f"Équipements inconnus : {', '.join(inconnus)}."
            )
        return value

    def validate(self, attrs):
        """
        RG : une secrétaire ne peut créer/modifier que des salles de sa filiale.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        filiale = attrs.get("filiale") or getattr(self.instance, "filiale", None)

        if user and user.role == "SECRETAIRE":
            if filiale is not None and filiale != user.filiale:
                raise serializers.ValidationError(
                    "Vous ne pouvez gérer que les salles de votre filiale."
                )
        return attrs
