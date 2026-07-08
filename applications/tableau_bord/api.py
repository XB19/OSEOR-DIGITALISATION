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

R = Reservation.Statut


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
        return Response(data)

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
