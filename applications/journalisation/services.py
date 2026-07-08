from .models import JournalAction


def enregistrer_action(acteur, action, cible="", objet=None, **details):
    """
    Enregistre une action dans le journal d'audit (EF-20).

    - acteur : utilisateur à l'origine (ou None pour une action système)
    - action : code (ex. "RESERVATION_VALIDEE")
    - cible  : description lisible
    - objet  : instance de modèle concernée (pour type + id), optionnel
    - details: paires clé/valeur additionnelles (sérialisables JSON)
    """
    objet_type = ""
    objet_id = None
    if objet is not None:
        objet_type = objet.__class__.__name__
        objet_id = getattr(objet, "pk", None)

    try:
        return JournalAction.objects.create(
            acteur=acteur if getattr(acteur, "pk", None) else None,
            action=action,
            cible=cible[:255],
            objet_type=objet_type,
            objet_id=objet_id,
            details=details or {},
        )
    except Exception:
        # La journalisation ne doit jamais bloquer l'action métier.
        return None
