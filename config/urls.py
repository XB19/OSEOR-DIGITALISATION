from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


def home_redirect(request):
    return redirect("login")


urlpatterns = [
    path("admin/", admin.site.urls),

    path("", home_redirect),

    path("auth/", include("applications.utilisateurs.urls")),
    path("dashboard/", include("applications.tableau_bord.urls")),
    path("filiales/", include("applications.filiales.urls")),
    path("reservations/", include("applications.reservations.urls")),
    path("salles/", include("applications.salles.urls")),
]