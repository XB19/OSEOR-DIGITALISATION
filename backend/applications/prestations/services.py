"""
Périmètre de visibilité des prestations et avancement par jalons.

Le périmètre est le service : un chef de service voit les prestations des
équipes qu'il dirige, pas celles du service voisin. C'est
`restreindre_au_service` (étape 2) qui porte cette règle, partagée avec les
autres modules.
"""

from datetime import date

from django.db.models import Q
from django.utils import timezone

from config.permissions import CHEF_SERVICE, est_direction

from .models import Prestation


def prestations_visibles(utilisateur):
    """
    Prestations que `utilisateur` peut consulter :

    - direction : tout le groupe ;
    - chef de service : les services qu'il dirige, plus le sien ;
    - intervenant ou responsable : les prestations où il figure, même hors
      de son service — on ne cache pas à quelqu'un le travail qu'il fait ;
    - autres : les prestations de leur service.
    """
    queryset = Prestation.objects.select_related(
        "filiale", "service", "responsable")

    if est_direction(utilisateur):
        return queryset

    if not (utilisateur and utilisateur.is_authenticated):
        return queryset.none()

    perimetre = Q(responsable=utilisateur) | Q(intervenants=utilisateur)

    if getattr(utilisateur, "service_id", None) is not None:
        perimetre |= Q(service_id=utilisateur.service_id)

    if utilisateur.role == CHEF_SERVICE:
        diriges = utilisateur.services_diriges.values_list("pk", flat=True)
        if diriges:
            perimetre |= Q(service_id__in=list(diriges))

    return queryset.filter(perimetre).distinct()


def peut_modifier(prestation, utilisateur):
    """
    Qui pilote une prestation : la direction, son responsable, et le chef
    du service qui la réalise.
    """
    if est_direction(utilisateur):
        return True
    if prestation.responsable_id == utilisateur.pk:
        return True
    return prestation.service.chef_id == utilisateur.pk


def generer_reference(filiale):
    """Référence lisible : KAPI-PRS-2026-0001."""
    annee = timezone.now().year
    rang = Prestation.objects.filter(
        filiale=filiale, date_creation__year=annee).count() + 1
    return f"{filiale.code}-PRS-{annee}-{rang:04d}"


def avancement(prestation):
    """
    Avancement mesuré sur les jalons réalisés, pas sur un pourcentage
    déclaré.

    Une prestation sans jalon renvoie None plutôt que 0 % : « aucun jalon
    défini » et « rien de fait » sont deux situations différentes, et les
    confondre ferait passer un dossier bien avancé pour un dossier à
    l'arrêt.
    """
    jalons = list(prestation.jalons.all())
    if not jalons:
        return None

    realises = [j for j in jalons if j.date_realisation is not None]

    return {
        "jalons": len(jalons),
        "realises": len(realises),
        "pourcentage": round(100 * len(realises) / len(jalons)),
        "prochain": next(
            (j.intitule for j in jalons if j.date_realisation is None), None),
        "jalons_en_retard": len([
            j for j in jalons
            if j.date_realisation is None and j.date_prevue < date.today()
        ]),
    }
