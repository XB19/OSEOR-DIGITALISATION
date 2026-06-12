from django.urls import path
from . import views

urlpatterns = [
    path("filiales/", views.filiale_list, name="filiale_list"),
    path("ajouter/", views.filiale_create, name="filiale_create"),
    path("modifier/<int:pk>/", views.filiale_update, name="filiale_update"),
    path("supprimer/<int:pk>/", views.filiale_delete, name="filiale_delete"),
]