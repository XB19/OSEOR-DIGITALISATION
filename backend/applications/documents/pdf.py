"""
Génération PDF d'un document administratif (Fiche de besoin, Demande
d'achat, Fiche de transport, Bon de sortie de caisse…) — la version
imprimable/archivable, circuit de visas et signatures scannées inclus.

Un seul générateur générique pour tous les types de documents : les colonnes
du tableau de lignes viennent de la configuration de la filiale (ou d'une
mise en page dédiée codée en dur pour la Fiche de transport, qui a sa propre
structure — cf. `_colonnes_lignes`).
"""

import io

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import Document, TypeDocument

User = get_user_model()

_COULEUR_ENTETE = colors.HexColor("#1e3a8a")
_COULEUR_TEXTE_2 = colors.HexColor("#64748b")
_COULEUR_LIGNE_ALT = colors.HexColor("#f8fafc")
_COULEUR_BORD = colors.HexColor("#cbd5e1")
_COULEUR_VALIDE = colors.HexColor("#15803d")
_COULEUR_REFUSE = colors.HexColor("#dc2626")

# Colonnes du tableau de lignes pour la Fiche de transport (mise en page
# dédiée, cf. le composant Angular équivalent) — pas configurable par filiale.
_COLONNES_FICHE_TRANSPORT = [
    ("date", "Date"), ("km_debut", "Km début"), ("km_fin", "Km fin"),
    ("frais_parking", "Frais parking"), ("lieu", "Lieu"), ("motif", "Motif"),
]

# Libellés lisibles des champs d'en-tête structurels par type de document.
_LIBELLES_CHAMPS_ENTETE = {
    "fournisseur": "Fournisseur", "reference": "Référence", "departement": "Département",
    "service": "Service", "beneficiaire": "Bénéficiaire", "montant_lettre": "Montant (en lettre)",
    "periode_debut": "Période — début", "periode_fin": "Période — fin",
    "km_precedent": "Km précédent", "km_actuel": "Km actuel", "taux_auto": "Taux au km",
    "km_domicile_bureau": "Km domicile — bureau", "statut_livraison": "Statut de livraison",
}


def _formater_date(valeur: str) -> str:
    dt = parse_datetime(valeur) if valeur else None
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M") if dt else (valeur or "")


def _image_signature(utilisateur) -> "RLImage | None":
    """Récupère la signature actuelle du profil de l'utilisateur, en image reportlab."""
    if not utilisateur or not utilisateur.signature:
        return None
    try:
        utilisateur.signature.open("rb")
        donnees = utilisateur.signature.read()
        utilisateur.signature.close()
        return RLImage(io.BytesIO(donnees), width=3.5 * cm, height=1.8 * cm, kind="proportional")
    except Exception:
        return None


def generer_pdf_document(document) -> bytes:
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=document.numero,
    )
    styles = getSampleStyleSheet()
    style_montant = ParagraphStyle("Montant", parent=styles["Normal"], alignment=TA_RIGHT, fontSize=12)
    style_section = ParagraphStyle("Section", parent=styles["Heading3"], spaceBefore=14, spaceAfter=6)
    style_sous_titre = ParagraphStyle("SousTitre", parent=styles["Normal"], fontSize=10, textColor=_COULEUR_TEXTE_2)
    style_pied = ParagraphStyle("Pied", parent=styles["Normal"], fontSize=7, textColor=_COULEUR_TEXTE_2)
    style_visa_fait = ParagraphStyle(
        "VisaFait", parent=styles["Normal"], borderPadding=6, spaceAfter=4, leading=14,
    )
    style_visa_attente = ParagraphStyle(
        "VisaAttente", parent=styles["Normal"], textColor=_COULEUR_TEXTE_2, spaceAfter=4,
    )

    elements = []

    # ---- En-tête ----
    elements.append(Paragraph(
        "<b>SMART HUB</b>",
        ParagraphStyle("Marque", fontSize=16, textColor=_COULEUR_ENTETE, spaceAfter=2, leading=20),
    ))
    elements.append(Paragraph(document.filiale.nom, style_sous_titre))
    elements.append(Spacer(1, 14))
    elements.append(Paragraph(f"{document.get_type_document_display()} — {document.numero}", styles["Heading2"]))
    elements.append(Paragraph(
        f"Demandeur : {document.demandeur.nom_complet} &nbsp;·&nbsp; "
        f"Date : {timezone.localtime(document.date_creation).strftime('%d/%m/%Y %H:%M')} &nbsp;·&nbsp; "
        f"Statut : <b>{document.get_statut_display()}</b>",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 14))

    config = document.configuration()

    # ---- Document source (ex. Demande d'achat à l'origine d'un Bon de commande) ----
    if document.document_source_id:
        elements.append(Paragraph(
            f"Émis à partir de la Demande d'achat <b>{document.document_source.numero}</b>",
            styles["Normal"],
        ))
        elements.append(Spacer(1, 6))

    # ---- Champs d'en-tête spécifiques (Demande d'achat, Fiche de transport…) ----
    if isinstance(document.champs_entete, dict) and document.champs_entete:
        libelles_statut_livraison = dict(Document.StatutLivraison.choices)
        lignes_entete = [
            [
                _LIBELLES_CHAMPS_ENTETE.get(cle, cle.replace("_", " ").capitalize()),
                libelles_statut_livraison.get(valeur, str(valeur)) if cle == "statut_livraison" else str(valeur),
            ]
            for cle, valeur in document.champs_entete.items() if valeur not in (None, "")
        ]
        if lignes_entete:
            t = Table(lignes_entete, colWidths=[5 * cm, 11 * cm])
            t.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), _COULEUR_TEXTE_2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 10))

    # ---- Tableau des lignes ----
    if document.type_document == TypeDocument.FICHE_TRANSPORT:
        colonnes = _COLONNES_FICHE_TRANSPORT
    elif config and config.colonnes:
        colonnes = [(c.get("cle"), c.get("libelle")) for c in config.colonnes]
    else:
        colonnes = []

    if colonnes and document.lignes:
        entetes = [libelle for _, libelle in colonnes]
        avec_difference = document.type_document == TypeDocument.FICHE_TRANSPORT
        if avec_difference:
            entetes.append("Différence")

        data = [entetes]
        for ligne in document.lignes:
            if not isinstance(ligne, dict):
                continue
            rangee = [str(ligne.get(cle, "") if ligne.get(cle) is not None else "") for cle, _ in colonnes]
            if avec_difference:
                diff = (ligne.get("km_fin") or 0) - (ligne.get("km_debut") or 0)
                rangee.append(str(max(diff, 0)))
            data.append(rangee)

        t = Table(data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _COULEUR_ENTETE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, _COULEUR_BORD),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COULEUR_LIGNE_ALT]),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8))

    if document.montant_total and float(document.montant_total) > 0:
        elements.append(Paragraph(f"<b>Montant total : {document.montant_total}</b>", style_montant))
        elements.append(Spacer(1, 6))

    if document.piece_jointe:
        nom_fichier = document.piece_jointe.name.rsplit("/", 1)[-1]
        elements.append(Paragraph(f"Pièce jointe : {nom_fichier} (consultable dans l'application)", styles["Normal"]))
        elements.append(Spacer(1, 6))

    # ---- Circuit de validation ----
    elements.append(Paragraph("Circuit de validation", style_section))
    visas = config.visas if config else []
    if not visas:
        elements.append(Paragraph("Aucun circuit de validation configuré.", style_visa_attente))

    for i, etape in enumerate(visas):
        libelle = etape.get("libelle", "")
        entree = next((h for h in document.historique_visas if h.get("etape") == i), None)

        if not entree:
            elements.append(Paragraph(f"<b>{libelle}</b> — en attente", style_visa_attente))
            continue

        decision = entree.get("decision")
        couleur = _COULEUR_VALIDE if decision == "VALIDE" else _COULEUR_REFUSE
        texte = (
            f"<b>{libelle}</b><br/>{entree.get('utilisateur_nom', '')} — "
            f"{'Validé' if decision == 'VALIDE' else 'Refusé'} le {_formater_date(entree.get('date'))}"
        )
        if entree.get("commentaire"):
            texte += f"<br/><i>« {entree['commentaire']} »</i>"

        style_etape = ParagraphStyle(
            f"Visa{i}", parent=style_visa_fait, textColor=couleur,
            borderColor=couleur, borderWidth=0.75,
        )
        elements.append(Paragraph(texte, style_etape))

        if entree.get("a_une_signature"):
            utilisateur = User.objects.filter(pk=entree.get("utilisateur_id")).first()
            image = _image_signature(utilisateur)
            if image:
                elements.append(image)
        elements.append(Spacer(1, 6))

    if document.motif_rejet:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(f"<b>Motif de refus :</b> {document.motif_rejet}", styles["Normal"]))

    elements.append(Spacer(1, 24))
    elements.append(Paragraph(
        f"Document généré automatiquement par SMART HUB le "
        f"{timezone.localtime(timezone.now()).strftime('%d/%m/%Y à %H:%M')}.",
        style_pied,
    ))

    doc.build(elements)
    tampon.seek(0)
    return tampon.getvalue()
