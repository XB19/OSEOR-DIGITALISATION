"""
Barème disciplinaire — Convention Collective Interprofessionnelle du Togo,
**article 58** (titre XII, Discipline).

Texte de référence :

    « Les sanctions disciplinaires applicables au personnel de l'entreprise
    ou de l'établissement en raison des fautes professionnelles commises ou
    des manquements à la discipline sont :

    a- L'avertissement avec inscription au dossier ;
    b- La mise à pied de un à huit jours avec privation de salaire ;
    c- La mise à pied aggravée de un à quinze jours avec privation de
       salaire ;
    d- Le licenciement avec préavis ;
    e- Le licenciement sans préavis en cas de faute lourde. »

Quatre règles de procédure encadrent ces sanctions, et ce sont elles que
le logiciel doit faire respecter — le barème seul ne protège personne :

1. **Le salarié s'explique d'abord.** « Les sanctions sont prononcées par
   écrit par le directeur de l'établissement **après que le travailleur
   assisté éventuellement de son délégué du personnel aura fourni ses
   explications écrites ou verbales**. »
2. **La sanction est écrite et signifiée**, avec ampliation à
   l'**Inspecteur du Travail** du ressort.
3. **Deux mois maximum.** « Dans tous les cas la sanction ne peut être
   infligée au-delà d'un délai de deux mois à compter de l'établissement
   de la preuve de la faute. »
4. **Non bis in idem.** « La même faute ne peut faire l'objet de deux
   sanctions. »

La **mise à pied conservatoire** n'est pas une sanction : c'est une mesure
d'attente, le temps d'instruire. La convention la mentionne expressément
pour les délégués du personnel en cas de faute lourde (« l'employeur peut
prononcer immédiatement sa mise à pied conservatoire en attendant la
décision définitive de l'Inspecteur du Travail ») ; elle est ici
disponible pour toute procédure, ce que la pratique admet, mais elle ne
préjuge d'aucune sanction et ne se substitue à aucune.
"""

#: Délai maximal entre l'établissement de la preuve et la sanction.
DELAI_SANCTION_MOIS = 2


class TypeSanction:
    """Échelle de l'article 58, du plus léger au plus grave."""

    AVERTISSEMENT = "AVERTISSEMENT"
    MISE_A_PIED = "MISE_A_PIED"
    MISE_A_PIED_AGGRAVEE = "MISE_A_PIED_AGGRAVEE"
    LICENCIEMENT_PREAVIS = "LICENCIEMENT_PREAVIS"
    LICENCIEMENT_SANS_PREAVIS = "LICENCIEMENT_SANS_PREAVIS"


#: Barème : libellé, durée admise, et exigence de faute lourde.
#:
#: - `jours_min` / `jours_max` : bornes de la privation de salaire ;
#:   None pour les sanctions qui ne se comptent pas en jours ;
#: - `faute_lourde_requise` : le licenciement sans préavis n'est ouvert
#:   qu'en cas de faute lourde (article 58 e).
BAREME = {
    TypeSanction.AVERTISSEMENT: {
        "libelle": "Avertissement avec inscription au dossier",
        "rang": 1,
        "jours_min": None,
        "jours_max": None,
        "faute_lourde_requise": False,
    },
    TypeSanction.MISE_A_PIED: {
        "libelle": "Mise à pied de 1 à 8 jours avec privation de salaire",
        "rang": 2,
        "jours_min": 1,
        "jours_max": 8,
        "faute_lourde_requise": False,
    },
    TypeSanction.MISE_A_PIED_AGGRAVEE: {
        "libelle": "Mise à pied aggravée de 1 à 15 jours avec privation de salaire",
        "rang": 3,
        "jours_min": 1,
        "jours_max": 15,
        "faute_lourde_requise": False,
    },
    TypeSanction.LICENCIEMENT_PREAVIS: {
        "libelle": "Licenciement avec préavis",
        "rang": 4,
        "jours_min": None,
        "jours_max": None,
        "faute_lourde_requise": False,
    },
    TypeSanction.LICENCIEMENT_SANS_PREAVIS: {
        "libelle": "Licenciement sans préavis (faute lourde)",
        "rang": 5,
        "jours_min": None,
        "jours_max": None,
        "faute_lourde_requise": True,
    },
}


#: Fautes lourdes énumérées par l'article 58.
#:
#: « Cette liste n'est pas limitative » — d'où le champ libre laissé sur la
#: procédure. Elle est reprise ici parce qu'elle est le point de départ de
#: toute qualification, et parce que « la violation du secret
#: professionnel » couvre expressément la compromission d'un système ou
#: d'un logiciel de l'entreprise.
FAUTES_LOURDES = [
    ("REFUS_TRAVAIL",
     "Refus d'exécuter un travail relevant de l'emploi"),
    ("VIOLATION_PRESCRIPTION",
     "Violation caractérisée d'une prescription de service"),
    ("MALVERSATION", "Malversation"),
    ("VOIES_DE_FAIT",
     "Voies de fait commises dans les locaux de l'établissement"),
    ("SECRET_PROFESSIONNEL",
     "Violation du secret professionnel"),
    ("IVRESSE", "État d'ivresse caractérisé"),
]


def regle(type_sanction):
    return BAREME.get(type_sanction)


def choix_sanctions():
    return [(code, r["libelle"]) for code, r in BAREME.items()]


def choix_fautes_lourdes():
    return list(FAUTES_LOURDES)


def duree_valide(type_sanction, jours):
    """
    Vérifie la durée d'une mise à pied contre les bornes de l'article 58.

    Renvoie un message d'erreur, ou None si la durée convient.
    """
    r = regle(type_sanction)
    if r is None:
        return "Sanction inconnue au barème de l'article 58."

    if r["jours_min"] is None:
        if jours:
            return f"« {r['libelle']} » ne se compte pas en jours."
        return None

    if not jours:
        return f"« {r['libelle']} » demande une durée."

    if not (r["jours_min"] <= jours <= r["jours_max"]):
        return (f"L'article 58 borne cette sanction à "
                f"{r['jours_min']}–{r['jours_max']} jours ; "
                f"{jours} demandé(s).")

    return None
