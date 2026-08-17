from django.urls import path
from . import views

urlpatterns = [
    path("", views.salle_list, name="salle_list"),
    path("ajouter/", views.salle_create, name="salle_create"),
    path("<int:pk>/modifier/", views.salle_update, name="salle_update"),
    path("<int:pk>/supprimer/", views.salle_delete, name="salle_delete"),
]