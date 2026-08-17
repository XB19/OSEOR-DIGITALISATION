from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static


def home_redirect(request):
    return redirect("login")


urlpatterns = [
    path("admin/", admin.site.urls),

    # API REST consommée par le frontend Angular
    path("api/", include("config.api_urls")),

    path("", home_redirect),

    # Interfaces Django legacy (non utilisées par le frontend Angular)
    path("auth/", include("applications.utilisateurs.urls")),
    path("dashboard/", include("applications.tableau_bord.urls")),
    path("filiales/", include("applications.filiales.urls")),
    path("reservations/", include("applications.reservations.urls")),
    path("salles/", include("applications.salles.urls")),
]

# Sert les fichiers média (photos de salles) en dev.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)