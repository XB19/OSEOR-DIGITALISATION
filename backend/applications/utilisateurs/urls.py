from django.urls import path
from .views import login_view, logout_view
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("utilisateurs/", views.utilisateur_list, name="utilisateur_list"),
    path("utilisateurs/ajouter/", views.utilisateur_create, name="utilisateur_create"),
    path("utilisateurs/<int:pk>/modifier/", views.utilisateur_update, name="utilisateur_update"),
    path("utilisateurs/<int:pk>/supprimer/", views.utilisateur_delete, name="utilisateur_delete"),
]