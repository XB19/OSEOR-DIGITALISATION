from rest_framework import serializers

from .models import LectureNote


class LectureNoteSerializer(serializers.ModelSerializer):
    """Une note reçue, vue par son destinataire."""

    numero = serializers.CharField(source="note.numero", read_only=True)
    objet = serializers.SerializerMethodField()
    corps = serializers.SerializerMethodField()
    redacteur_nom = serializers.CharField(
        source="note.demandeur.nom_complet", read_only=True)
    filiale_nom = serializers.CharField(source="note.filiale.nom", read_only=True)
    lue = serializers.BooleanField(read_only=True)

    class Meta:
        model = LectureNote
        fields = (
            "id", "note", "numero", "objet", "corps",
            "redacteur_nom", "filiale_nom",
            "lue", "date_diffusion", "date_lecture",
        )
        read_only_fields = fields

    def get_objet(self, obj) -> str:
        return (obj.note.champs_entete or {}).get("objet", "")

    def get_corps(self, obj) -> str:
        return (obj.note.champs_entete or {}).get("corps", "")
