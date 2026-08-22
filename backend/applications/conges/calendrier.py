"""
Calendrier ouvré : jours fériés togolais et décompte des jours ouvrés.

Fonctions volontairement pures là où c'est possible (`paques`,
`feries_calcules`, `est_ouvre`) : ce sont elles qui décident combien de
jours un salarié perd sur son solde, et une erreur d'un jour se voit sur
une fiche de paie. Elles se testent sans base de données.

La semaine ouvrée retenue est **lundi-vendredi**. Si une filiale du groupe
travaille le samedi, c'est ici qu'il faut intervenir.
"""

from datetime import date, timedelta

from .models import JourFerie

#: Samedi et dimanche (`date.weekday()` : lundi = 0).
WEEK_END = (5, 6)

#: Jours fériés togolais à date fixe.
#:
#: À faire confirmer par les RH : cette liste est le point de départ, pas
#: une référence légale. Elle est de toute façon surchargeable en base,
#: puisque les jours fériés sont des données et non du code.
FERIES_FIXES = [
    ((1, 1), "Jour de l'An"),
    ((1, 13), "Fête de la Libération nationale"),
    ((4, 27), "Fête de l'Indépendance"),
    ((5, 1), "Fête du Travail"),
    ((6, 21), "Journée des Martyrs"),
    ((8, 15), "Assomption"),
    ((11, 1), "Toussaint"),
    ((12, 25), "Noël"),
]

#: Décalages par rapport au dimanche de Pâques.
FERIES_MOBILES = [
    (1, "Lundi de Pâques"),
    (39, "Ascension"),
    (50, "Lundi de Pentecôte"),
]


def paques(annee):
    """
    Dimanche de Pâques (algorithme grégorien anonyme).

    Sert à placer le Lundi de Pâques, l'Ascension et le Lundi de Pentecôte,
    qui se déduisent tous de cette date.
    """
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois, jour = divmod(h + l - 7 * m + 114, 31)
    return date(annee, mois, jour + 1)


def feries_calcules(annee):
    """
    Jours fériés togolais d'une année : dates fixes et dates déduites de
    Pâques.

    **N'inclut pas l'Aïd el-Fitr ni l'Aïd el-Adha** : ces fêtes suivent le
    calendrier lunaire et sont fixées chaque année par décret. Elles se
    saisissent à la main (admin Django ou `JourFerie`), ce qui est aussi la
    raison pour laquelle les jours fériés sont une table et non une
    constante.

    Renvoie une liste de couples (date, intitulé), triée.
    """
    resultat = [
        (date(annee, mois, jour), nom)
        for (mois, jour), nom in FERIES_FIXES
    ]

    dimanche_paques = paques(annee)
    resultat += [
        (dimanche_paques + timedelta(days=decalage), nom)
        for decalage, nom in FERIES_MOBILES
    ]

    return sorted(resultat)


def est_ouvre(jour, feries=()):
    """True si `jour` est un jour travaillé (hors week-end et hors férié)."""
    if jour.weekday() in WEEK_END:
        return False
    return jour not in feries


def feries_entre(debut, fin, filiale=None):
    """
    Dates fériées enregistrées entre `debut` et `fin`, pour une filiale :
    les fériés du groupe (sans filiale) plus ceux propres à la filiale.
    """
    queryset = JourFerie.objects.filter(date__gte=debut, date__lte=fin)

    if filiale is not None:
        queryset = queryset.filter(filiale__isnull=True) | queryset.filter(
            filiale=filiale)
    else:
        queryset = queryset.filter(filiale__isnull=True)

    return set(queryset.values_list("date", flat=True))


def jours_ouvres(debut, fin, filiale=None):
    """
    Liste des jours ouvrés entre `debut` et `fin`, bornes incluses.

    Renvoie une liste vide si l'intervalle est inversé — au lieu de lever :
    l'appelant valide déjà l'ordre des dates, et un décompte négatif serait
    bien plus dangereux qu'un zéro.
    """
    if debut > fin:
        return []

    feries = feries_entre(debut, fin, filiale)

    resultat = []
    jour = debut
    while jour <= fin:
        if est_ouvre(jour, feries):
            resultat.append(jour)
        jour += timedelta(days=1)

    return resultat


def compter_jours_ouvres(debut, fin, filiale=None):
    """Nombre de jours ouvrés entre `debut` et `fin`, bornes incluses."""
    return len(jours_ouvres(debut, fin, filiale))
