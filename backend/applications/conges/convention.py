"""
Barème des permissions exceptionnelles — Convention Collective
Interprofessionnelle du Togo (CCIT révisée du 12 décembre 2011),
**article 45**.

Texte de référence, cité mot pour mot :

    « Des permissions d'absences exceptionnelles, dans les limites fixées
    ci-dessous, **non déductibles du congé annuel et n'entraînant aucune
    réduction de salaire**, peuvent être accordées au travailleur ayant au
    moins six mois d'ancienneté dans l'entreprise […]

    - À l'occasion d'évènements familiaux, **même si le travailleur ne
      justifie pas de six mois d'ancienneté** dans l'entreprise. »

Deux conséquences directes sur le code :

1. une permission ne débite jamais le solde de congé annuel — d'où son
   absence de `TYPES_DECOMPTES` ;
2. l'ancienneté de six mois s'applique aux permissions syndicales, mais
   **pas** aux évènements familiaux.

Barème inscrit ici plutôt qu'en base : ce sont des minima conventionnels,
identiques pour toutes les filiales du groupe. Une entreprise peut faire
mieux, jamais moins — d'où `jours` interprété comme un plafond de droit,
contrôlé à la saisie.
"""

#: Délai de production du justificatif (article 45) : « le document
#: attestant l'évènement doit être présenté à l'employeur dans le plus bref
#: délai et au plus tard huit jours après que l'évènement ait eu lieu ».
DELAI_JUSTIFICATIF_JOURS = 8

#: « En ce qui concerne la naissance au foyer, le travailleur conserve son
#: droit au congé dans la limite maximale de six mois après l'évènement. »
DELAI_NAISSANCE_MOIS = 6

#: Ancienneté exigée par défaut (article 45, premier alinéa).
ANCIENNETE_REQUISE_MOIS = 6


class MotifPermission:
    """Codes des motifs, pour éviter les chaînes libres dans le code."""

    DECES_CONJOINT_ASCENDANT_DESCENDANT = "DECES_PROCHE"
    DECES_FRERE_SOEUR = "DECES_FRATRIE"
    DECES_BEAU_PARENT = "DECES_BEAU_PARENT"
    MARIAGE_TRAVAILLEUR = "MARIAGE_TRAVAILLEUR"
    MARIAGE_PROCHE = "MARIAGE_PROCHE"
    NAISSANCE = "NAISSANCE"
    BAPTEME = "BAPTEME"
    DEMENAGEMENT = "DEMENAGEMENT"
    CONGRES_SYNDICAL = "CONGRES_SYNDICAL"
    SEMINAIRE_SYNDICAL_NATIONAL = "SEMINAIRE_SYNDICAL"


#: Barème de l'article 45.
#:
#: - `jours`            : droit maximal pour l'évènement ;
#: - `familial`         : True = dispensé de la condition d'ancienneté ;
#: - `justificatif`     : pièce à produire sous 8 jours ;
#: - `plafond_annuel`   : limite par année civile (permissions syndicales),
#:                        None si l'évènement n'en a pas.
BAREME = {
    MotifPermission.DECES_CONJOINT_ASCENDANT_DESCENDANT: {
        "libelle": "Décès d'un conjoint, d'un ascendant ou d'un descendant "
                   "en ligne directe",
        "jours": 4,
        "familial": True,
        "justificatif": "Acte de décès",
        "plafond_annuel": None,
    },
    MotifPermission.DECES_FRERE_SOEUR: {
        "libelle": "Décès d'un frère ou d'une sœur",
        "jours": 2,
        "familial": True,
        "justificatif": "Acte de décès",
        "plafond_annuel": None,
    },
    MotifPermission.DECES_BEAU_PARENT: {
        "libelle": "Décès d'un beau-père ou d'une belle-mère",
        "jours": 3,
        "familial": True,
        "justificatif": "Acte de décès",
        "plafond_annuel": None,
    },
    MotifPermission.MARIAGE_TRAVAILLEUR: {
        "libelle": "Mariage du travailleur",
        "jours": 3,
        "familial": True,
        "justificatif": "Acte de mariage",
        "plafond_annuel": None,
    },
    MotifPermission.MARIAGE_PROCHE: {
        "libelle": "Mariage d'un enfant, d'un frère ou d'une sœur",
        "jours": 1,
        "familial": True,
        "justificatif": "Acte de mariage",
        "plafond_annuel": None,
    },
    MotifPermission.NAISSANCE: {
        "libelle": "Naissance au foyer",
        "jours": 2,
        "familial": True,
        "justificatif": "Certificat de naissance",
        "plafond_annuel": None,
    },
    MotifPermission.BAPTEME: {
        "libelle": "Baptême",
        "jours": 1,
        "familial": True,
        "justificatif": "Certificat de baptême",
        "plafond_annuel": None,
    },
    MotifPermission.DEMENAGEMENT: {
        "libelle": "Déménagement",
        "jours": 1,
        "familial": True,
        "justificatif": "Justificatif de domicile",
        "plafond_annuel": None,
    },
    MotifPermission.CONGRES_SYNDICAL: {
        "libelle": "Congrès professionnel syndical",
        "jours": 10,
        "familial": False,
        "justificatif": "Convocation syndicale",
        "plafond_annuel": 10,
    },
    MotifPermission.SEMINAIRE_SYNDICAL_NATIONAL: {
        "libelle": "Séminaire syndical national",
        "jours": 30,
        "familial": False,
        "justificatif": "Convocation syndicale",
        "plafond_annuel": 30,
    },
}


def choix_motifs():
    """Couples (code, libellé) pour les `choices` Django et l'API."""
    return [(code, regle["libelle"]) for code, regle in BAREME.items()]


def regle(motif):
    """Règle applicable à un motif, ou None si le motif est inconnu."""
    return BAREME.get(motif)


def jours_accordes(motif):
    """Droit maximal en jours pour ce motif."""
    regle_motif = regle(motif)
    return regle_motif["jours"] if regle_motif else 0


def exige_anciennete(motif):
    """
    True si le motif est soumis à la condition de six mois d'ancienneté.

    Les évènements familiaux en sont expressément dispensés par
    l'article 45 ; les permissions syndicales, non.
    """
    regle_motif = regle(motif)
    if regle_motif is None:
        return True
    return not regle_motif["familial"]
