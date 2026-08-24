from datetime import date, timedelta

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response

from applications.journalisation.services import enregistrer_action
from config.permissions import est_direction

from .models import Evenement
from .serializers import EvenementSerializer, EvenementEcritureSerializer
from . import services

#: Fenêtre par défaut du calendrier quand l'appelant ne précise rien.
FENETRE_PAR_DEFAUT_JOURS = 60


class EvenementViewSet(viewsets.ModelViewSet):
    """
    Événements de la vie interne : cérémonies, discours, fêtes, réceptions.

    Chacun voit selon la visibilité de l'événement (groupe, filiale,
    service) ; seul le créateur, un chef de service, une secrétaire ou la
    direction peuvent modifier ou supprimer.
    """

    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ("type_evenement", "filiale", "service", "annule")
    search_fields = ("titre", "description", "lieu")
    ordering_fields = ("date_debut", "titre")

    #: Rôles autorisés à modifier un événement dont ils ne sont pas l'auteur.
    ROLES_GESTION = ("SECRETAIRE", "CHEF_SERVICE")

    def get_queryset(self):
        return services.evenements_visibles(self.request.user)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return EvenementEcritureSerializer
        return EvenementSerializer

    def _peut_modifier(self, evenement):
        utilisateur = self.request.user
        return (
            est_direction(utilisateur)
            or evenement.createur_id == utilisateur.pk
            or utilisateur.role in self.ROLES_GESTION
        )

    def _refus_modification(self):
        return Response(
            {"detail": "Seuls l'auteur, un gestionnaire ou la direction "
                       "peuvent modifier cet événement."},
            status=status.HTTP_403_FORBIDDEN,
        )

    def update(self, request, *args, **kwargs):
        if not self._peut_modifier(self.get_object()):
            return self._refus_modification()
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        evenement = self.get_object()
        if not self._peut_modifier(evenement):
            return self._refus_modification()
        enregistrer_action(
            request.user, "EVENEMENT_SUPPRIME", evenement.titre, objet=evenement)
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        evenement = serializer.save()
        enregistrer_action(
            self.request.user, "EVENEMENT_CREE", evenement.titre, objet=evenement)

    @action(detail=False, methods=["get"])
    def calendrier(self, request):
        """
        Vue calendrier : événements saisis et anniversaires calculés sur une
        même fenêtre de dates.

        Paramètres `debut` et `fin` au format AAAA-MM-JJ ; à défaut, les
        60 jours à venir.
        """
        try:
            debut = self._date_parametre(request, "debut", date.today())
            fin = self._date_parametre(
                request, "fin", debut + timedelta(days=FENETRE_PAR_DEFAUT_JOURS))
        except ValueError:
            return Response(
                {"detail": "Dates attendues au format AAAA-MM-JJ."}, status=400)

        if fin < debut:
            return Response(
                {"detail": "La fin ne peut pas précéder le début."}, status=400)

        evenements = self.get_queryset().filter(
            date_debut__date__lte=fin, date_fin__date__gte=debut, annule=False,
        )

        return Response({
            "debut": debut,
            "fin": fin,
            "evenements": EvenementSerializer(
                evenements, many=True, context={"request": request}).data,
            "anniversaires": services.anniversaires(debut, fin, request.user),
        })

    @staticmethod
    def _date_parametre(request, nom, defaut):
        brut = request.query_params.get(nom)
        return date.fromisoformat(brut) if brut else defaut
