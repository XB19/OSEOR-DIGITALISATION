import unicodedata

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import ADMINISTRATEUR, LectureTousEcriture

from .models import EntreeAide
from .serializers import EntreeAideSerializer

#: Nombre maximum de suggestions renvoyées pour une question posée.
MAX_SUGGESTIONS = 3


def _normaliser(texte: str) -> str:
    """Minuscule et sans accents, pour un matching indépendant de la casse/accentuation."""
    texte = texte.lower().strip()
    texte = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in texte if not unicodedata.combining(c))


def _score(question_normalisee: str, entree: EntreeAide) -> int:
    """
    Score de pertinence d'une entrée pour la question posée : un mot-clé
    présent dans la question compte pour 1 (2 s'il s'agit d'une expression
    de plusieurs mots, plus spécifique), et un fort recouvrement avec la
    question canonique de l'entrée ajoute un bonus.
    """
    score = 0
    for mot_cle in entree.mots_cles.split(","):
        mot_cle = _normaliser(mot_cle)
        if mot_cle and mot_cle in question_normalisee:
            score += 2 if " " in mot_cle else 1

    question_entree = _normaliser(entree.question)
    if question_entree in question_normalisee or question_normalisee in question_entree:
        score += 3

    return score


class EntreeAideViewSet(viewsets.ModelViewSet):
    """Référentiel de questions/réponses du chatbot d'aide."""

    serializer_class = EntreeAideSerializer
    permission_classes = [LectureTousEcriture(ADMINISTRATEUR)]
    filterset_fields = ("module", "actif")

    def get_queryset(self):
        queryset = EntreeAide.objects.all()
        if self.request.query_params.get("actif") is None:
            queryset = queryset.filter(actif=True)
        return queryset

    @action(detail=False, methods=["get"])
    def modules(self, request):
        """Modules disponibles et nombre d'entrées actives, pour les catégories du chatbot."""
        libelles = dict(EntreeAide.Module.choices)
        presents = (
            EntreeAide.objects.filter(actif=True)
            .values_list("module", flat=True)
            .distinct()
        )
        comptes = {
            m: EntreeAide.objects.filter(actif=True, module=m).count() for m in presents
        }
        resultats = [
            {"module": m, "libelle": libelles.get(m, m), "count": comptes[m]}
            for m in EntreeAide.Module.values
            if m in comptes
        ]
        return Response(resultats)

    @action(detail=False, methods=["post"])
    def poser_question(self, request):
        """Cherche les meilleures réponses à une question posée en texte libre."""
        question = str(request.data.get("question", ""))
        question_normalisee = _normaliser(question)

        if not question_normalisee:
            return Response({"trouve": False, "resultats": []})

        notees = [
            (entree, _score(question_normalisee, entree))
            for entree in EntreeAide.objects.filter(actif=True)
        ]
        pertinentes = sorted(
            (n for n in notees if n[1] > 0),
            key=lambda n: (-n[1], n[0].module, n[0].ordre),
        )[:MAX_SUGGESTIONS]

        resultats = EntreeAideSerializer([e for e, _ in pertinentes], many=True).data
        return Response({"trouve": bool(resultats), "resultats": resultats})
