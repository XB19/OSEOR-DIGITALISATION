from django.contrib.auth import get_user_model
from django.utils import timezone

from applications.notifications.services import envoyer_notification

from .models import Contrat

User = get_user_model()

# Jours restants avant échéance déclenchant une alerte (une seule fois
# chacun, par contrat — cf. `seuils_alertes_envoyes`).
SEUILS_ALERTE_JOURS = [30, 15, 7, 3, 1]


def _notifier_echeance(contrat, titre, message):
    destinataires = set()
    if contrat.cree_par_id:
        destinataires.add(contrat.cree_par)
    destinataires.update(User.objects.filter(filiale=contrat.filiale, role="CHEF_SERVICE", is_active=True))
    for u in destinataires:
        envoyer_notification(u, titre, message, "WARNING", objet=contrat)

    for admin in User.objects.filter(role="ADMINISTRATEUR", is_active=True):
        envoyer_notification(admin, f"Suivi — {titre}", f"{message} ({contrat.filiale.nom})", "INFO", objet=contrat)


def verifier_echeances_et_alerter(queryset=None):
    """
    Fait progresser le statut des contrats venus à échéance (ACTIF -> EXPIRE)
    et envoie les alertes d'approche d'échéance (30/15/7/3/1 jours avant).

    Idempotent : chaque seuil n'est notifié qu'une seule fois par contrat
    (`seuils_alertes_envoyes`), donc rejouable sans risque de doublons.

    Appelée à la fois par la commande de gestion `verifier_echeances_contrats`
    (à programmer en tâche planifiée quotidienne — ex. Planificateur de
    tâches Windows, aucun ordonnanceur de tâches périodiques n'existe encore
    dans ce projet) et, en best-effort, à chaque consultation de la liste des
    contrats — pour que les alertes fonctionnent même sans tâche planifiée
    configurée.
    """
    qs = queryset if queryset is not None else Contrat.objects.all()
    contrats = (
        qs.exclude(statut=Contrat.Statut.RESILIE)
        .filter(date_echeance__isnull=False)
        .select_related("filiale", "cree_par")
    )
    aujourdhui = timezone.localdate()

    for contrat in contrats:
        jours = (contrat.date_echeance - aujourdhui).days
        seuils = list(contrat.seuils_alertes_envoyes)
        modifie = False

        if jours < 0:
            if contrat.statut != Contrat.Statut.EXPIRE:
                contrat.statut = Contrat.Statut.EXPIRE
                modifie = True
            if "EXPIRE" not in seuils:
                _notifier_echeance(
                    contrat, "Contrat expiré",
                    f"{contrat.numero} — {contrat.intitule} est arrivé à échéance le "
                    f"{contrat.date_echeance.strftime('%d/%m/%Y')}.",
                )
                seuils.append("EXPIRE")
                modifie = True
        else:
            # Si plusieurs seuils sont franchis d'un coup (ex. contrat
            # enregistré alors que l'échéance est déjà proche, ou vérification
            # sautée quelques jours), on n'envoie qu'UNE alerte — pas une par
            # seuil dépassé — mais on marque bien tous les seuils dépassés
            # comme notifiés pour ne pas les redéclencher plus tard.
            seuils_franchis = [s for s in SEUILS_ALERTE_JOURS if jours <= s and s not in seuils]
            if seuils_franchis:
                _notifier_echeance(
                    contrat, "Échéance de contrat proche",
                    f"{contrat.numero} — {contrat.intitule} arrive à échéance dans {jours} jour(s) "
                    f"({contrat.date_echeance.strftime('%d/%m/%Y')}).",
                )
                seuils.extend(seuils_franchis)
                modifie = True

        if modifie:
            contrat.seuils_alertes_envoyes = seuils
            contrat.save(update_fields=["statut", "seuils_alertes_envoyes", "date_modification"])


def notifier_resiliation(contrat, acteur):
    titre = "Contrat résilié"
    message = f"{contrat.numero} — {contrat.intitule} a été résilié par {acteur.nom_complet}."
    for admin in User.objects.filter(role="ADMINISTRATEUR", is_active=True):
        envoyer_notification(admin, f"Suivi — {titre}", f"{message} ({contrat.filiale.nom})", "INFO", objet=contrat)
    if contrat.cree_par_id and contrat.cree_par_id != acteur.id:
        envoyer_notification(contrat.cree_par, titre, message, "INFO", objet=contrat)
