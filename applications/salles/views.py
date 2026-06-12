from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from .models import Salle
from applications.filiales.models import Filiale
from django.db.models import Q


# =========================
# LISTE
# =========================
@login_required
def salle_list(request):

    user = request.user

    if user.role == "ADMINISTRATEUR":
        salles = Salle.objects.all()

    elif user.role == "CHEF_SERVICE":
        salles = Salle.objects.filter(
Q(filiale=user.filiale) | Q(est_salle_groupe=True)
        )

    else:
        return redirect("dashboard")

    return render(request, "salles/salle_list.html", {
        "salles": salles
    })


# =========================
# CREATE
# =========================
@login_required
def salle_create(request):

    user = request.user

    if user.role not in ["ADMINISTRATEUR", "CHEF_SERVICE"]:
        return redirect("dashboard")

    filiales = Filiale.objects.all()

    if request.method == "POST":

        filiale_id = request.POST.get("filiale")
        if filiale_id == "":
            filiale_id = None

        salle = Salle.objects.create(
            nom=request.POST.get("nom"),
            capacite=request.POST.get("capacite"),
            description=request.POST.get("description"),
            est_salle_groupe=request.POST.get("est_salle_groupe") == "on",
            filiale_id=filiale_id,
        )

        salle.equipements = request.POST.getlist("equipements")
        salle.save()

        return redirect("salle_list")

    return render(request, "salles/salle_form.html", {
        "filiales": filiales
    })


# =========================
# UPDATE
# =========================
@login_required
def salle_update(request, pk):

    user = request.user
    salle = get_object_or_404(Salle, pk=pk)

    if user.role == "CHEF_SERVICE" and salle.filiale != user.filiale:
        return redirect("dashboard")

    if request.method == "POST":

        salle.nom = request.POST.get("nom")
        salle.capacite = request.POST.get("capacite")
        salle.description = request.POST.get("description")
        salle.est_salle_groupe = bool(request.POST.get("est_salle_groupe"))
        salle.filiale_id = request.POST.get("filiale") or None

        salle.equipements = request.POST.getlist("equipements")

        salle.save()

        return redirect("salle_list")

    filiales = Filiale.objects.all()

    return render(request, "salles/salle_form.html", {
        "salle": salle,
        "filiales": filiales
    })


# =========================
# DELETE
# =========================
@login_required
def salle_delete(request, pk):

    user = request.user
    salle = get_object_or_404(Salle, pk=pk)

    if user.role == "CHEF_SERVICE" and salle.filiale != user.filiale:
        return redirect("dashboard")

    salle.delete()

    return redirect("salle_list")