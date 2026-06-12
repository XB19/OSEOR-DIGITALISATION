from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from applications.utilisateurs.models import Utilisateur
from applications.filiales.models import Filiale
from applications.salles.models import Salle
from applications.reservations.models import Reservation
from django.db.models import Q


@login_required
def dashboard(request):

    user = request.user

    context = {}

    # ================= ADMINISTRATEUR =================
    if user.role == "ADMINISTRATEUR":

        context = {
            "total_users": Utilisateur.objects.count(),
            "total_filiales": Filiale.objects.count(),
            "total_salles": Salle.objects.count(),

            "reservations_attente": Reservation.objects.filter(
                statut="EN_ATTENTE"
            ).count(),
        }

    # ================= DIRECTEUR / GERANT =================
    elif user.role == "DIRECTEUR":

        context = {
            "salles_disponibles": Salle.objects.filter(
                filiale=user.filiale
            ).count(),

            "reservations_attente": Reservation.objects.filter(
                salle__filiale=user.filiale,
                statut="EN_ATTENTE"
            ).count(),

            "reservations_validees": Reservation.objects.filter(
                salle__filiale=user.filiale,
                statut="CONFIRMEE"
            ).count(),
        }

            # ================= CHEF_SERVICE =================

    elif user.role == "CHEF_SERVICE":

        salles_qs = Salle.objects.filter(
            Q(filiale=user.filiale) |
            Q(est_salle_groupe=True)
        )

        context = {
            "salles_disponibles": salles_qs.count(),

            "reservations_attente": Reservation.objects.filter(
                Q(salle__filiale=user.filiale) |
                Q(salle__est_salle_groupe=True),
                statut="EN_ATTENTE"
            ).count(),

            "reservations_validees": Reservation.objects.filter(
                Q(salle__filiale=user.filiale) |
                Q(salle__est_salle_groupe=True),
                statut="CONFIRMEE"
            ).count(),
        }


    # ================= EMPLOYE =================
    else:

        context = {
            "mes_reservations": Reservation.objects.filter(
                demandeur=user
            ).count(),

            "mes_attentes": Reservation.objects.filter(
                demandeur=user,
                statut="EN_ATTENTE"
            ).count(),

            "mes_validees": Reservation.objects.filter(
                demandeur=user,
                statut="CONFIRMEE"
            ).count(),
        }

    return render(request, "tableau_bord/dashboard.html", context)