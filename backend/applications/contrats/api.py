from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from config.permissions import GereLesContrats
from applications.journalisation.services import enregistrer_action
from .models import Contrat, PieceJointeContrat
from .serializers import ContratSerializer, ContratEcritureSerializer
from .services import verifier_echeances_et_alerter, notifier_resiliation


class ContratViewSet(viewsets.ModelViewSet):
    """
    Registre des contrats (fournisseur, client, prestation, bail…) — chaque
    filiale gère les siens. Pas de suppression : un contrat obsolète se
    résilie (`resilier`), il ne s'efface jamais, pour garder la traçabilité.
    """

    http_method_names = ["get", "post", "patch", "head", "options"]
    filterset_fields = ("type_contrat", "statut", "filiale")
    search_fields = ("numero", "intitule", "partie_contractante", "reference")
    ordering_fields = ("date_creation", "date_echeance")
    permission_classes = [GereLesContrats]

    def get_queryset(self):
        qs = Contrat.objects.select_related("filiale", "cree_par").prefetch_related("pieces_jointes")
        u = self.request.user
        if u.role in ("ADMINISTRATEUR", "DIRECTEUR"):
            return qs
        return qs.filter(filiale=u.filiale)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ContratEcritureSerializer
        return ContratSerializer

    def get_serializer_context(self):
        return {"request": self.request}

    def list(self, request, *args, **kwargs):
        # Best-effort : garantit que les alertes d'échéance fonctionnent même
        # si la commande planifiée `verifier_echeances_contrats` n'est pas
        # configurée sur la machine hôte. Ne doit jamais faire échouer la
        # consultation de la liste.
        try:
            verifier_echeances_et_alerter(self.get_queryset())
        except Exception:
            pass
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contrat = serializer.save()
        enregistrer_action(request.user, "CONTRAT_CREE", f"{contrat.numero} — {contrat.intitule}", objet=contrat)
        return Response(
            ContratSerializer(contrat, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", True)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        contrat = serializer.save()
        enregistrer_action(request.user, "CONTRAT_MODIFIE", f"{contrat.numero} — {contrat.intitule}", objet=contrat)
        return Response(ContratSerializer(contrat, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def resilier(self, request, pk=None):
        contrat = self.get_object()
        if contrat.statut == Contrat.Statut.RESILIE:
            return Response({"detail": "Ce contrat est déjà résilié."}, status=400)

        contrat.statut = Contrat.Statut.RESILIE
        contrat.motif_resiliation = (request.data.get("motif") or "").strip()
        contrat.date_resiliation = timezone.localdate()
        contrat.save(update_fields=["statut", "motif_resiliation", "date_resiliation", "date_modification"])

        enregistrer_action(request.user, "CONTRAT_RESILIE", f"{contrat.numero} — {contrat.intitule}", objet=contrat)
        notifier_resiliation(contrat, request.user)
        return Response(ContratSerializer(contrat, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["post"])
    def ajouter_piece_jointe(self, request, pk=None):
        contrat = self.get_object()
        fichier = request.FILES.get("fichier")
        if not fichier:
            return Response({"detail": "Aucun fichier fourni."}, status=400)

        PieceJointeContrat.objects.create(
            contrat=contrat, fichier=fichier, nom_original=fichier.name, ajoute_par=request.user,
        )
        enregistrer_action(
            request.user, "PIECE_JOINTE_CONTRAT_AJOUTEE", f"{contrat.numero} — {fichier.name}", objet=contrat,
        )
        # `contrat` vient de get_object(), dont le cache "pieces_jointes"
        # (prefetch_related de get_queryset) a été figé avant l'ajout :
        # refresh_from_db() vide ce cache pour refléter la nouvelle pièce.
        contrat.refresh_from_db()
        return Response(
            ContratSerializer(contrat, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def supprimer_piece_jointe(self, request, pk=None):
        contrat = self.get_object()
        piece = contrat.pieces_jointes.filter(pk=request.data.get("piece_jointe")).first()
        if not piece:
            return Response({"detail": "Pièce jointe introuvable."}, status=404)

        nom = piece.nom_original or piece.fichier.name
        piece.fichier.delete(save=False)
        piece.delete()
        enregistrer_action(
            request.user, "PIECE_JOINTE_CONTRAT_SUPPRIMEE", f"{contrat.numero} — {nom}", objet=contrat,
        )
        contrat.refresh_from_db()
        return Response(ContratSerializer(contrat, context=self.get_serializer_context()).data)

    @action(detail=False, methods=["get"])
    def alertes_echeance(self, request):
        """Contrats actifs dont l'échéance est dans les 30 prochains jours ou dépassée."""
        qs = self.get_queryset().exclude(statut=Contrat.Statut.RESILIE).filter(date_echeance__isnull=False)
        proches = sorted(
            (c for c in qs if c.jours_avant_echeance is not None and c.jours_avant_echeance <= 30),
            key=lambda c: c.date_echeance,
        )
        return Response(ContratSerializer(proches, many=True, context=self.get_serializer_context()).data)
