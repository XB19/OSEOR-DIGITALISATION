from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Filiale


# =========================
# LISTE
# =========================
@login_required
def filiale_list(request):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    filiales = Filiale.objects.all()

    return render(request, "filiales/filiale_list.html", {
        "filiales": filiales
    })


# =========================
# CREATE
# =========================
@login_required
def filiale_create(request):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    if request.method == "POST":

        Filiale.objects.create(
            nom=request.POST["nom"],
            code=request.POST["code"],
            email=request.POST.get("email"),
            telephone=request.POST.get("telephone"),
            adresse=request.POST.get("adresse"),
            description=request.POST.get("description"),
        )

        return redirect("filiale_list")

    return render(request, "filiales/filiale_form.html")


# =========================
# UPDATE
# =========================
@login_required
def filiale_update(request, pk):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    filiale = get_object_or_404(Filiale, pk=pk)

    if request.method == "POST":

        filiale.nom = request.POST["nom"]
        filiale.code = request.POST["code"]
        filiale.email = request.POST.get("email")
        filiale.telephone = request.POST.get("telephone")
        filiale.adresse = request.POST.get("adresse")
        filiale.description = request.POST.get("description")

        filiale.save()

        return redirect("filiale_list")

    return render(request, "filiales/filiale_form.html", {
        "filiale_obj": filiale
    })


# =========================
# DELETE
# =========================
@login_required
def filiale_delete(request, pk):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    filiale = get_object_or_404(Filiale, pk=pk)
    filiale.delete()

    return redirect("filiale_list")