from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from applications.filiales.models import Filiale
from applications.salles.models import Salle
from applications.reservations.models import Reservation
from applications.audiences.models import Audience
from applications.visiteurs.models import Visite
from applications.contrats.models import Contrat
from applications.stocks.models import Article
from applications.caisse.models import BonSortie
from applications.notes.models import LectureNote
from applications.discipline.models import ProcedureDisciplinaire
from applications.discipline.services import procedures_visibles
from applications.conges.models import DemandeConge
from applications.conges.workflow import peut_valider as conges_peut_valider
from applications.documents.models import TypeDocument
from applications.documents.services import compter_a_viser_par_type
from config.permissions import RH, est_direction, restreindre_a_la_filiale

R = Reservation.Statut

# Type de document -> (route Angular, icône) — même correspondance que
# `CHEMIN_PAR_TYPE_DOCUMENT` côté frontend (core/modules-metier.ts), les
# deux copies devant évoluer ensemble si un type de document est ajouté.
_ROUTE_PAR_TYPE_DOCUMENT = {
    TypeDocument.FICHE_BESOIN: ("/fiche-besoin", "send"),
    TypeDocument.DEMANDE_ACHAT: ("/demandes-achat", "cart"),
    TypeDocument.FICHE_TRANSPORT: ("/deplacements", "car"),
    TypeDocument.BON_SORTIE_CAISSE: ("/bon-sortie-caisse", "wallet"),
    TypeDocument.BON_COMMANDE: ("/bons-commande", "cart"),
    TypeDocument.NOTE_INTERNE: ("/notes-internes", "edit"),
    TypeDocument.FACTURE: ("/factures", "receipt"),
}


class StatistiquesView(APIView):
    """
    Indicateurs du tableau de bord (EF Q-F), adaptés au rôle et à la filiale.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        aujourd_hui = timezone.localdate()
        debut_mois = aujourd_hui.replace(day=1)

        if u.role == "ADMINISTRATEUR":
            salles = Salle.objects.all()
            reservations = Reservation.objects.all()
            audiences = Audience.objects.all()
            data = {
                "portee": "groupe",
                "nb_filiales": Filiale.objects.filter(active=True).count(),
            }
        elif u.role == "SECRETAIRE":
            salles = Salle.objects.filter(filiale=u.filiale)
            reservations = Reservation.objects.filter(salle__filiale=u.filiale)
            audiences = Audience.objects.filter(secretaire=u)
            data = {"portee": "filiale", "filiale": u.filiale.nom if u.filiale else None}
        elif u.role == "DIRECTEUR":
            salles = Salle.objects.filter(filiale=u.filiale)
            reservations = Reservation.objects.filter(salle__filiale=u.filiale)
            audiences = Audience.objects.filter(dg=u)
            data = {"portee": "direction", "filiale": u.filiale.nom if u.filiale else None}
        else:  # employé
            salles = Salle.objects.all()
            reservations = Reservation.objects.filter(demandeur=u)
            audiences = Audience.objects.none()
            data = {"portee": "personnel"}

        # Comptages réservations en UNE seule requête (agrégation conditionnelle)
        rstats = reservations.aggregate(
            total=Count("id"),
            attente=Count("id", filter=Q(statut=R.EN_ATTENTE)),
            validees=Count("id", filter=Q(statut=R.VALIDEE)),
        )
        # Comptages audiences en UNE seule requête
        termine = [Audience.Statut.CONFIRMEE, Audience.Statut.TERMINEE, Audience.Statut.ANNULEE]
        astats = audiences.aggregate(
            du_mois=Count("id", filter=Q(date_creation__date__gte=debut_mois)),
            en_cours=Count("id", filter=~Q(statut__in=termine)),
        )

        data.update({
            "nb_salles": salles.filter(active=True).count(),
            "reservations_en_attente": rstats["attente"],
            "reservations_validees": rstats["validees"],
            "reservations_total": rstats["total"],
            "audiences_du_mois": astats["du_mois"],
            "audiences_en_cours": astats["en_cours"],
            "taux_occupation_7j": self._taux_occupation(salles, aujourd_hui),
            "salles_plus_demandees": self._salles_top(reservations),
        })
        data["mes_actions"] = self._mes_actions(u, rstats["attente"])
        return Response(data)

    def _mes_actions(self, u, reservations_en_attente):
        """
        Ce que CET utilisateur a personnellement à valider ou consulter,
        tous modules confondus — pas seulement les réservations de salles.
        Une entrée par élément avec un compteur > 0 ; rien à afficher = rien
        de renvoyé (le front affiche alors un état vide).
        """
        actions = []

        if u.role in ("SECRETAIRE", "ADMINISTRATEUR") and reservations_en_attente:
            actions.append({
                "cle": "reservations", "libelle": "Réservations à valider",
                "count": reservations_en_attente, "lien": "/validation", "icone": "checkCircle",
            })

        if u.role in ("SECRETAIRE", "ADMINISTRATEUR", "DIRECTEUR"):
            n = restreindre_a_la_filiale(
                Visite.objects.filter(statut=Visite.Statut.EN_ATTENTE), u
            ).count()
            if n:
                actions.append({
                    "cle": "visites", "libelle": "Visiteurs à valider",
                    "count": n, "lien": "/visiteurs", "icone": "idCard",
                })

        # Congés : même périmètre que conges/api.py::get_queryset (RH et
        # direction voient tout, les autres leurs subordonnés + eux-mêmes),
        # puis on ne garde que les demandes où c'est réellement à cet
        # utilisateur de trancher (conges.workflow.peut_valider).
        if est_direction(u) or u.role == RH:
            demandes = DemandeConge.objects.filter(statut=DemandeConge.Statut.EN_ATTENTE)
        else:
            subordonnes = u.subordonnes.values_list("pk", flat=True)
            demandes = DemandeConge.objects.filter(
                statut=DemandeConge.Statut.EN_ATTENTE, utilisateur__in=[u.pk, *subordonnes],
            )
        n = sum(1 for d in demandes if conges_peut_valider(d, u))
        if n:
            actions.append({
                "cle": "conges", "libelle": "Congés à valider",
                "count": n, "lien": "/conges", "icone": "sun",
            })

        if u.role in ("CHEF_SERVICE", "DIRECTEUR", "ADMINISTRATEUR"):
            contrats = Contrat.objects.exclude(statut=Contrat.Statut.RESILIE).filter(date_echeance__isnull=False)
            if u.role not in ("ADMINISTRATEUR", "DIRECTEUR"):
                contrats = contrats.filter(filiale=u.filiale)
            n = sum(1 for c in contrats if c.jours_avant_echeance is not None and c.jours_avant_echeance <= 30)
            if n:
                actions.append({
                    "cle": "contrats", "libelle": "Contrats proches de l'échéance",
                    "count": n, "lien": "/contrats", "icone": "briefcase",
                })

            articles = Article.objects.filter(actif=True)
            if u.role not in ("ADMINISTRATEUR", "DIRECTEUR"):
                articles = articles.filter(filiale=u.filiale)
            n = sum(1 for a in articles if a.en_alerte)
            if n:
                actions.append({
                    "cle": "stocks", "libelle": "Articles en alerte de stock",
                    "count": n, "lien": "/stocks", "icone": "archive",
                })

        # Bons de sortie de caisse : même filtre que caisse/api.py::a_autoriser.
        bons = BonSortie.objects.filter(statut=BonSortie.Statut.EN_ATTENTE).exclude(demandeur=u)
        if not est_direction(u):
            bons = bons.filter(destinataire=u)
        n = bons.count()
        if n:
            actions.append({
                "cle": "bons_sortie", "libelle": "Bons de sortie à autoriser",
                "count": n, "lien": "/bon-sortie-caisse", "icone": "wallet",
            })

        n = LectureNote.objects.filter(destinataire=u, date_lecture__isnull=True).count()
        if n:
            actions.append({
                "cle": "notes", "libelle": "Notes non lues",
                "count": n, "lien": "/notes-recues", "icone": "doc",
            })

        if est_direction(u) or u.role == RH:
            n = procedures_visibles(u).filter(
                statut__in=[
                    ProcedureDisciplinaire.Statut.OUVERTE,
                    ProcedureDisciplinaire.Statut.EXPLICATIONS_FOURNIES,
                ]
            ).count()
            if n:
                actions.append({
                    "cle": "discipline", "libelle": "Procédures disciplinaires en cours",
                    "count": n, "lien": "/discipline", "icone": "shield",
                })

        # Documents à viser : une entrée par type de document (Fiche de
        # besoin, Demande d'achat…), chacune vers sa propre page.
        for type_document, n in compter_a_viser_par_type(u).items():
            route_icone = _ROUTE_PAR_TYPE_DOCUMENT.get(type_document)
            if not route_icone or not n:
                continue
            lien, icone = route_icone
            actions.append({
                "cle": f"documents_{type_document.lower()}",
                "libelle": f"{TypeDocument(type_document).label} à viser",
                "count": n, "lien": lien, "icone": icone,
            })

        return actions

    def _taux_occupation(self, salles, debut):
        """
        Taux d'occupation moyen des salles sur les 7 prochains jours,
        sur une amplitude de bureau 8h-18h (10h/jour ouvré).
        """
        fin = debut + timedelta(days=7)
        nb_salles = salles.filter(active=True).count()
        if not nb_salles:
            return 0.0

        reservations = Reservation.objects.filter(
            salle__in=salles,
            statut__in=Reservation.STATUTS_ACTIFS,
            date_reunion__gte=debut,
            date_reunion__lt=fin,
        ).values("heure_debut", "heure_fin")

        heures_reservees = 0.0
        for r in reservations:
            delta = (
                r["heure_fin"].hour * 60 + r["heure_fin"].minute
                - r["heure_debut"].hour * 60 - r["heure_debut"].minute
            ) / 60.0
            heures_reservees += max(delta, 0)

        # 5 jours ouvrés * 10h * nb_salles
        capacite = 5 * 10 * nb_salles
        return round(100 * heures_reservees / capacite, 1) if capacite else 0.0

    def _salles_top(self, reservations):
        top = (
            reservations.filter(statut__in=Reservation.STATUTS_ACTIFS)
            .values("salle__nom")
            .annotate(total=Count("id"))
            .order_by("-total")[:5]
        )
        return [{"salle": t["salle__nom"], "reservations": t["total"]} for t in top]
