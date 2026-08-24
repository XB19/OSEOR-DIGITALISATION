from django.contrib.auth import get_user_model

from applications.notifications.services import envoyer_notification

User = get_user_model()


def notifier_seuil_alerte(article):
    """
    Le stock d'un article vient d'atteindre (ou de descendre sous) son seuil
    d'alerte : notifie les Chefs de service de la filiale (habilités à
    réapprovisionner) et, pour suivi, les administrateurs.
    """
    titre = "Seuil d'alerte de stock atteint"
    message = (
        f"{article.nom} — {article.quantite_stock} {article.unite}(s) restant(s) "
        f"(seuil : {article.seuil_alerte})."
    )

    chefs_service = User.objects.filter(
        filiale=article.filiale, role="CHEF_SERVICE", is_active=True,
    )
    for u in chefs_service:
        envoyer_notification(u, titre, message, "WARNING", objet=article)

    admins = User.objects.filter(role="ADMINISTRATEUR", is_active=True)
    for admin in admins:
        envoyer_notification(
            admin, f"Suivi — {titre}",
            f"{article.nom} ({article.filiale.nom}) — {article.quantite_stock} {article.unite}(s) restant(s).",
            "INFO", objet=article,
        )
