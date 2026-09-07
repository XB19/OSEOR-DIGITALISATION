from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import (
    ADMINISTRATEUR, AGENT_SECURITE, DIRECTEUR, SECRETAIRE,
    EstUnDes, est_direction,
)
from applications.journalisation.services import enregistrer_action

from .models import Visite
from .pdf import generer_pdf_registre_visiteurs
from .serializers import VisiteSerializer
from .services import marquer_depart_visite, refuser_visite, valider_visite


class VisiteViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    Registre des visiteurs de l'accueil. L'agent de sécurité enregistre une
    demande, la secrétaire (ou la direction) la valide ou la refuse, puis
    l'agent marque le départ quand le visiteur récupère sa pièce
    d'identité — même circuit que la validation des réservations de
    salles, adapté à deux acteurs.
    """

    serializer_class = VisiteSerializer
    permission_classes = [EstUnDes(AGENT_SECURITE, SECRETAIRE, ADMINISTRATEUR, DIRECTEUR)]
    filterset_fields = ("statut",)
    ordering_fields = ("heure_arrivee",)

    def get_queryset(self):
        """
        L'agent de sécurité tient un accueil commun à tout le groupe : il
        voit les visites de toutes les filiales, pas seulement la sienne
        (`restreindre_a_la_filiale` ne convient pas ici). La secrétaire, en
        revanche, ne s'occupe que des visiteurs de sa propre filiale.
        """
        u = self.request.user
        qs = Visite.objects.select_related(
            "filiale", "personne_visitee", "enregistre_par", "traite_par"
        )
        if est_direction(u) or u.role == AGENT_SECURITE:
            return qs
        return qs.filter(filiale_id=u.filiale_id) if u.filiale_id else qs.none()

    def perform_create(self, serializer):
        visite = serializer.save()
        enregistrer_action(
            self.request.user, "VISITE_ENREGISTREE",
            f"{visite.prenom} {visite.nom} — {visite.motif}",
            objet=visite,
        )

    # ------------------------------------------------------------------
    # Validation par le secrétariat (même logique que RG-02 côté réservations)
    # ------------------------------------------------------------------
    def _peut_traiter(self, request) -> bool:
        return request.user.role in (SECRETAIRE, ADMINISTRATEUR, DIRECTEUR)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        visite = self.get_object()
        if not self._peut_traiter(request):
            return Response(
                {"detail": "Seul le secrétariat peut valider une demande de visite."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if visite.statut != Visite.Statut.EN_ATTENTE:
            return Response(
                {"detail": "Seule une demande en attente peut être validée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        valider_visite(visite, request.user)
        enregistrer_action(
            request.user, "VISITE_VALIDEE",
            f"{visite.prenom} {visite.nom}",
            objet=visite,
        )
        return Response(VisiteSerializer(visite).data)

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        visite = self.get_object()
        if not self._peut_traiter(request):
            return Response(
                {"detail": "Seul le secrétariat peut refuser une demande de visite."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if visite.statut != Visite.Statut.EN_ATTENTE:
            return Response(
                {"detail": "Seule une demande en attente peut être refusée."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        motif = request.data.get("motif", "")
        refuser_visite(visite, request.user, motif)
        enregistrer_action(
            request.user, "VISITE_REFUSEE",
            f"{visite.prenom} {visite.nom}",
            objet=visite, motif=motif,
        )
        return Response(VisiteSerializer(visite).data)

    # ------------------------------------------------------------------
    # Départ : l'agent de sécurité rend la pièce d'identité au visiteur
    # ------------------------------------------------------------------
    @action(detail=True, methods=["post"])
    def marquer_depart(self, request, pk=None):
        visite = self.get_object()
        if visite.statut != Visite.Statut.VALIDEE:
            return Response(
                {"detail": "Seul un visiteur validé et toujours présent peut être marqué comme parti."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        marquer_depart_visite(visite)
        enregistrer_action(
            request.user, "VISITE_TERMINEE",
            f"{visite.prenom} {visite.nom}",
            objet=visite,
        )
        return Response(VisiteSerializer(visite).data)

    # ------------------------------------------------------------------
    # Registre imprimable — même périmètre (filiale) que la consultation
    # ------------------------------------------------------------------
    @action(detail=False, methods=["get"])
    def registre(self, request):
        visites = list(self.get_queryset().order_by("-heure_arrivee"))
        u = request.user
        filiale_nom = "Groupe (toutes filiales)" if (est_direction(u) or u.role == AGENT_SECURITE) else (
            u.filiale.nom if u.filiale_id else "—"
        )
        contenu = generer_pdf_registre_visiteurs(visites, filiale_nom)

        reponse = HttpResponse(contenu, content_type="application/pdf")
        horodatage = timezone.localdate().isoformat()
        reponse["Content-Disposition"] = f'attachment; filename="registre_visiteurs_{horodatage}.pdf"'
        return reponse
