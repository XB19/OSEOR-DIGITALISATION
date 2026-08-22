"""
Seed des configurations de documents (colonnes + chaîne de visas) par
filiale, à partir des fiches papier réellement utilisées par chaque
entreprise du groupe. Ré-exécutable : met à jour les configurations
existantes plutôt que de les dupliquer.

Usage : python manage.py seed_config_documents
"""

from django.core.management.base import BaseCommand

from applications.filiales.models import Filiale
from applications.documents.models import ConfigurationDocument, TypeDocument

# Colonnes par défaut du tableau de lignes, par type de document.
COLONNES_DEFAUT = {
    TypeDocument.FICHE_BESOIN: [
        {"cle": "motif", "libelle": "Besoin et motifs"},
        {"cle": "beneficiaire", "libelle": "Bénéficiaire"},
        {"cle": "quantite", "libelle": "Quantité"},
    ],
    TypeDocument.DEMANDE_ACHAT: [
        {"cle": "designation", "libelle": "Désignation"},
        {"cle": "motif", "libelle": "Motif"},
        {"cle": "qte", "libelle": "Qté"},
        {"cle": "puht", "libelle": "PUHT"},
        {"cle": "montant", "libelle": "Montant"},
    ],
    TypeDocument.FICHE_TRANSPORT: [
        {"cle": "lieu", "libelle": "Lieu"},
        {"cle": "motif", "libelle": "Motif"},
        {"cle": "montant", "libelle": "Montant"},
    ],
    TypeDocument.BON_SORTIE_CAISSE: [
        {"cle": "compte_debit", "libelle": "Compte débit"},
        {"cle": "compte_credit", "libelle": "Compte crédit"},
        {"cle": "montant_debit", "libelle": "Montant débit"},
        {"cle": "montant_credit", "libelle": "Montant crédit"},
        {"cle": "objet", "libelle": "Objet ou motif de sortie de caisse"},
    ],
    # Une note de service n'a pas de tableau de lignes : son contenu tient
    # dans l'objet et le corps, portes par champs_entete.
    TypeDocument.NOTE_INTERNE: [],
}

# Chaînes de visas par défaut, par type de document (utilisées quand
# l'entreprise n'a pas de fiche spécifique fournie).
VISAS_DEFAUT = {
    TypeDocument.FICHE_BESOIN: [
        {"cle": "demandeur", "libelle": "Visa du Demandeur"},
        {"cle": "chef_comptable", "libelle": "Visa du Chef Comptable", "role": "COMPTABLE"},
        {"cle": "directeur_general", "libelle": "Visa du Directeur Général", "role": "DIRECTEUR"},
    ],
    TypeDocument.DEMANDE_ACHAT: [
        {"cle": "demandeur", "libelle": "Visa du Demandeur"},
        {"cle": "chef_service", "libelle": "Visa du Chef de Service", "role": "CHEF_SERVICE"},
        {"cle": "directeur_general", "libelle": "Visa du Directeur Général", "role": "DIRECTEUR"},
    ],
    TypeDocument.FICHE_TRANSPORT: [
        {"cle": "demandeur", "libelle": "Signature"},
        {"cle": "secretaire", "libelle": "Signature de la secrétaire", "role": "SECRETAIRE"},
        {"cle": "comptable", "libelle": "Signature du comptable", "role": "COMPTABLE"},
    ],
    TypeDocument.BON_SORTIE_CAISSE: [
        {"cle": "demandeur", "libelle": "Demandeur"},
        {"cle": "chef_service_dep", "libelle": "Visa Chef Sce Dép.", "role": "CHEF_SERVICE"},
        {"cle": "resp_tresorerie", "libelle": "Visa Resp. Trésorerie", "role": "COMPTABLE"},
        {"cle": "finance_comptabilite", "libelle": "Visa Finance Comptabilité", "role": "COMPTABLE"},
    ],
    # La note n'est diffusée qu'une fois signée par la direction.
    TypeDocument.NOTE_INTERNE: [
        {"cle": "redacteur", "libelle": "Rédigée par"},
        {"cle": "directeur_general", "libelle": "Visa du Directeur Général", "role": "DIRECTEUR"},
    ],
}

# Surcharges par filiale (code) — reflètent exactement les fiches papier
# fournies pour cette entreprise, quand elles diffèrent du modèle par défaut.
SURCHARGES = {
    ("OSEOR", TypeDocument.FICHE_BESOIN): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.FICHE_BESOIN],
        "visas": VISAS_DEFAUT[TypeDocument.FICHE_BESOIN],
    },
    ("KAPI", TypeDocument.FICHE_BESOIN): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.FICHE_BESOIN],
        "visas": [
            {"cle": "demandeur", "libelle": "Visa du Demandeur"},
            {"cle": "comptable", "libelle": "Visa du Comptable", "role": "COMPTABLE"},
            {"cle": "directeur_general", "libelle": "Visa du Directeur Général", "role": "DIRECTEUR"},
        ],
    },
    ("ZIH", TypeDocument.FICHE_BESOIN): {
        "colonnes": [
            {"cle": "motif", "libelle": "Besoin et motifs"},
            {"cle": "beneficiaire", "libelle": "Bénéficiaire"},
            {"cle": "montant", "libelle": "Montant"},
        ],
        "visas": [
            {"cle": "demandeur", "libelle": "Visa du Demandeur"},
            {"cle": "chef_comptable", "libelle": "Visa du Chef Comptable", "role": "COMPTABLE"},
            {"cle": "secretaire_general", "libelle": "Visa du Secrétaire Général", "role": "DIRECTEUR"},
        ],
    },
    ("DIWA", TypeDocument.DEMANDE_ACHAT): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.DEMANDE_ACHAT],
        "visas": [
            {"cle": "demandeur", "libelle": "Établi par (Demandeur)"},
            {"cle": "chef_departement", "libelle": "Visa Chef département", "role": "CHEF_SERVICE"},
            {"cle": "achats_moyens_generaux", "libelle": "Visa du Service Achats et Moyens Généraux", "role": "SECRETAIRE"},
            {"cle": "controle_budget", "libelle": "Visa Contrôle & Budget", "role": "COMPTABLE"},
            {"cle": "dfc", "libelle": "Visa du D.F.C", "role": "COMPTABLE"},
            {"cle": "directeur_general", "libelle": "Approbation du Directeur Général", "role": "DIRECTEUR"},
        ],
    },
    ("DIWA", TypeDocument.BON_SORTIE_CAISSE): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.BON_SORTIE_CAISSE],
        "visas": VISAS_DEFAUT[TypeDocument.BON_SORTIE_CAISSE],
    },
    ("KAPI", TypeDocument.FICHE_TRANSPORT): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.FICHE_TRANSPORT],
        "visas": VISAS_DEFAUT[TypeDocument.FICHE_TRANSPORT],
    },
    ("AROBASE", TypeDocument.FICHE_TRANSPORT): {
        "colonnes": COLONNES_DEFAUT[TypeDocument.FICHE_TRANSPORT],
        "visas": [
            {"cle": "demandeur", "libelle": "Signature"},
            {"cle": "caissiere", "libelle": "Signature de la Caissière", "role": "COMPTABLE"},
            {"cle": "comptable", "libelle": "Signature du comptable", "role": "COMPTABLE"},
        ],
    },
}


class Command(BaseCommand):
    help = "Crée/actualise les configurations de documents (colonnes + visas) par filiale."

    def handle(self, *args, **options):
        total = 0
        for filiale in Filiale.objects.all():
            for type_document in TypeDocument.values:
                surcharge = SURCHARGES.get((filiale.code, type_document))
                colonnes = (surcharge or {}).get("colonnes", COLONNES_DEFAUT[type_document])
                visas = (surcharge or {}).get("visas", VISAS_DEFAUT[type_document])

                config, cree = ConfigurationDocument.objects.update_or_create(
                    filiale=filiale, type_document=type_document,
                    defaults={"colonnes": colonnes, "visas": visas},
                )
                total += 1
                action = "créée" if cree else "mise à jour"
                self.stdout.write(f"  {filiale.code} / {type_document} — configuration {action}")

        self.stdout.write(self.style.SUCCESS(f"{total} configuration(s) traitée(s)."))
