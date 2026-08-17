from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from applications.reservations.models import Reservation
from applications.salles.models import Salle
from django.utils import timezone


@login_required
def reservation_create(request):

    user = request.user

    # =========================
    # ACCÈS AUTORISÉS
    # =========================
    if user.role not in ["EMPLOYE", "ADMINISTRATEUR", "DIRECTEUR", "CHEF_SERVICE"]:
        return redirect("dashboard")

    # =========================
    # SALLES VISIBLES
    # =========================
    # RG-03 : un employé peut réserver une salle de n'importe quelle filiale.
    if user.role in ["ADMINISTRATEUR", "EMPLOYE", "CHEF_SERVICE", "DIRECTEUR"]:
        salles = Salle.objects.filter(active=True)

    else:
        salles = Salle.objects.none()

    # =========================
    # POST (CREATION RESERVATION)
    # =========================
    if request.method == "POST":

        salle_id = request.POST.get("salle")

        if not salle_id:
            return redirect("reservation_create")

        # sécurité : salle doit être dans les salles autorisées
        salle = get_object_or_404(salles, id=salle_id)

        nom_reservant = request.POST.get("nom_reservant") or user.nom_complet
        date_reunion = request.POST.get("date_reunion")
        heure_debut = request.POST.get("heure_debut")
        heure_fin = request.POST.get("heure_fin")
        precisions = request.POST.get("precisions", "")

        # =========================
        # VALIDATIONS SIMPLES
        # =========================
        if not date_reunion or not heure_debut or not heure_fin:
            return redirect("reservation_create")

        if heure_debut >= heure_fin:
            return redirect("reservation_create")

        # =========================
        # CREATION
        # =========================
        Reservation.objects.create(
            demandeur=user,
            nom_reservant=nom_reservant,
            salle=salle,
            date_reunion=date_reunion,
            heure_debut=heure_debut,
            heure_fin=heure_fin,
            precisions=precisions,
            statut=Reservation.Statut.EN_ATTENTE
        )

        return redirect("reservation_list")

    # =========================
    # CONTEXT
    # =========================
    return render(request, "reservations/reservation_form.html", {
        "salles": salles
    })


from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from applications.reservations.models import Reservation


@login_required
@login_required
def reservation_list(request):

    reservations = Reservation.objects.all()

    print("TOTAL RESERVATIONS:", reservations.count())

    return render(request, "reservations/reservation_list.html", {
        "reservations": reservations
    })


@login_required
def reservation_valider(request, pk):

    user = request.user

    reservation = get_object_or_404(Reservation, pk=pk)

    if user.role != "CHEF_SERVICE":
        return redirect("dashboard")

    reservation.statut = Reservation.Statut.VALIDEE
    reservation.valide_par = user
    reservation.date_validation = timezone.now()
    reservation.save()

    return redirect("reservation_list")


@login_required
def reservation_refuser(request, pk):

    user = request.user

    reservation = get_object_or_404(Reservation, pk=pk)

    if user.role != "CHEF_SERVICE":
        return redirect("dashboard")

    reservation.statut = Reservation.Statut.REFUSEE
    reservation.valide_par = user
    reservation.date_validation = timezone.now()
    reservation.save()

    return redirect("reservation_list")



@login_required
def reservation_mes_reservations(request):

    user = request.user

    reservations = Reservation.objects.filter(
        demandeur=user
    ).order_by("-date_creation")

    return render(request, "reservations/reservation_mes.html", {
        "reservations": reservations
    })