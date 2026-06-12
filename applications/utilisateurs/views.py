from django.shortcuts import render

# Create your views here.
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from applications.utilisateurs.models import Utilisateur
from applications.filiales.models import Filiale


def login_view(request):

    if request.method == "POST":

        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            if user.role == "ADMIN_PRINCIPAL":
                return redirect("dashboard")

            elif user.role == "GERANT":
                return redirect("dashboard")

            return redirect("dashboard")

        return render(
            request,
            "utilisateurs/auth/login.html",
            {"error": "Identifiants invalides"}
        )

    return render(
        request,
        "utilisateurs/auth/login.html"
    )

from django.contrib.auth import logout
from django.shortcuts import redirect

def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
def utilisateur_list(request):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    users = Utilisateur.objects.all()

    return render(request, "utilisateurs/utilisateur_list.html", {
        "users": users
    })


@login_required
@login_required
def utilisateur_create(request):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    filiales = Filiale.objects.all()

    if request.method == "POST":

        user = Utilisateur.objects.create_user(
            username=request.POST["username"],
            password=request.POST["password"],
            first_name=request.POST.get("first_name"),
            last_name=request.POST.get("last_name"),
            email=request.POST.get("email"),
        )

        user.role = request.POST["role"]
        user.filiale_id = request.POST.get("filiale") or None
        user.save()

        return redirect("utilisateur_list")

    return render(request, "utilisateurs/utilisateur_form.html", {
        "filiales": filiales,
        "roles": Utilisateur.Role.choices
    })


@login_required
def utilisateur_update(request, pk):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    user = get_object_or_404(Utilisateur, pk=pk)
    filiales = Filiale.objects.all()

    if request.method == "POST":

        user.first_name = request.POST["first_name"]
        user.last_name = request.POST["last_name"]
        user.email = request.POST["email"]
        user.role = request.POST["role"]
        user.filiale_id = request.POST.get("filiale")

        user.save()

        return redirect("utilisateur_list")

    return render(request, "utilisateurs/utilisateur_form.html", {
        "user_obj": user,
        "filiales": filiales
    })


@login_required
def utilisateur_delete(request, pk):

    if request.user.role != "ADMINISTRATEUR":
        return redirect("dashboard")

    user = get_object_or_404(Utilisateur, pk=pk)

    user.delete()

    return redirect("utilisateur_list")


