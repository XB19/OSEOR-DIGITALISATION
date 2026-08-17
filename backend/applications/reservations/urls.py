from django.urls import path
from . import views

urlpatterns = [
    path("reservation_list/", views.reservation_list, name="reservation_list"),
    path("mes-reservations/", views.reservation_mes_reservations, name="reservation_mes_reservations"),
    path("ajouter/", views.reservation_create, name="reservation_create"),
    path("valider/<int:pk>/", views.reservation_valider, name="reservation_valider"),
    path("refuser/<int:pk>/", views.reservation_refuser, name="reservation_refuser"),
]