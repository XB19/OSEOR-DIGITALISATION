"""
Génération PDF du rapport administratif (consolidation documents, contrats,
stocks) — même esprit que `applications.documents.pdf` : un vrai document
imprimable/archivable, pas un export brut de données, avec synthèse en
introduction, indicateurs clés mis en avant, et tableaux détaillés par section.
"""

import io

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_COULEUR_ENTETE = colors.HexColor("#1e3a8a")   # var(--navy)
_COULEUR_ACCENT = colors.HexColor("#f97316")   # var(--accent)
_COULEUR_VERT = colors.HexColor("#16a34a")     # var(--vert)
_COULEUR_BLEU = colors.HexColor("#2563eb")     # var(--bleu)
_COULEUR_TEXTE_2 = colors.HexColor("#64748b")
_COULEUR_LIGNE_ALT = colors.HexColor("#f8fafc")
_COULEUR_BORD = colors.HexColor("#e2e8f0")

# (libellé, clé du rapport -> valeur formatée, couleur d'accent)
_KPI_COULEURS = [_COULEUR_VERT, _COULEUR_ENTETE, _COULEUR_ACCENT, _COULEUR_BLEU, _COULEUR_ACCENT]


def _fmt_montant(valeur, decimales=0) -> str:
    """Formate un montant avec séparateur de milliers (espace insécable), à la française."""
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return str(valeur)
    texte = f"{nombre:,.{decimales}f}"
    return texte.replace(",", " ")


def _entete_tableau(couleur=_COULEUR_ENTETE):
    return [
        ("BACKGROUND", (0, 0), (-1, 0), couleur),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.5, _COULEUR_BORD),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _COULEUR_LIGNE_ALT]),
    ]


def _pied_page(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(_COULEUR_BORD)
    canvas.line(1.5 * cm, 1.35 * cm, A4[0] - 1.5 * cm, 1.35 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(_COULEUR_TEXTE_2)
    genere_le = timezone.localtime(timezone.now()).strftime("%d/%m/%Y à %H:%M")
    canvas.drawString(1.5 * cm, 1 * cm, f"SMART HUB — Rapport généré automatiquement le {genere_le}")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, f"Page {doc.page}")
    canvas.restoreState()


def generer_pdf_rapport_administratif(rapport: dict, date_debut, date_fin) -> bytes:
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(
        tampon, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.8 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        title=f"Rapport administratif {date_debut} - {date_fin}",
    )
    styles = getSampleStyleSheet()
    style_marque = ParagraphStyle("Marque", fontSize=16, textColor=_COULEUR_ENTETE, leading=20)
    style_sous_titre = ParagraphStyle("SousTitre", parent=styles["Normal"], fontSize=10, textColor=_COULEUR_TEXTE_2)
    style_section = ParagraphStyle("Section", parent=styles["Heading3"], spaceBefore=16, spaceAfter=6, textColor=_COULEUR_ENTETE)
    style_synthese = ParagraphStyle("Synthese", parent=styles["Normal"], fontSize=10, leading=15)
    style_kpi_valeur = ParagraphStyle("KpiValeur", fontSize=15, leading=18, fontName="Helvetica-Bold", alignment=TA_CENTER)
    style_kpi_libelle = ParagraphStyle("KpiLibelle", fontSize=7.5, leading=10, textColor=_COULEUR_TEXTE_2, alignment=TA_CENTER)

    elements = []

    # ---- En-tête ----
    elements.append(Paragraph("<b>SMART HUB</b>", style_marque))
    elements.append(Paragraph("Groupe OSEOR", style_sous_titre))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Rapport administratif", styles["Title"]))
    elements.append(Paragraph(
        f"Périmètre : <b>{rapport['filiale']}</b> &nbsp;·&nbsp; "
        f"Période : <b>du {date_debut.strftime('%d/%m/%Y')} au {date_fin.strftime('%d/%m/%Y')}</b>",
        style_sous_titre,
    ))
    elements.append(Spacer(1, 16))

    # ---- Synthèse ----
    d, c, s = rapport["documents"], rapport["contrats"], rapport["stocks"]
    elements.append(Paragraph(
        f"Sur cette période, <b>{d['total_documents']}</b> document(s) administratif(s) ont été traités pour "
        f"<b>{_fmt_montant(d['montant_total_valide'])}</b> validé(s), <b>{c['actifs']}</b> contrat(s) sont actifs "
        f"(<b>{_fmt_montant(c['montant_engage'])}</b> engagés) et <b>{s['mouvements_total']}</b> mouvement(s) de "
        f"stock ont été enregistrés." + (
            f" <b>{s['articles_en_alerte']}</b> article(s) sont actuellement en alerte de stock."
            if s["articles_en_alerte"] else ""
        ),
        style_synthese,
    ))
    elements.append(Spacer(1, 14))

    # ---- Indicateurs clés ----
    kpis = [
        (_fmt_montant(d["montant_total_valide"]), "Montant validé\n(documents)"),
        (_fmt_montant(c["montant_engage"]), "Montant engagé\n(contrats actifs)"),
        (str(c["echeances_proches_30j"]), "Échéances de\ncontrat < 30j"),
        (str(s["mouvements_total"]), "Mouvements\nde stock"),
        (str(s["articles_en_alerte"]), "Articles en\nalerte de stock"),
    ]
    ligne_valeurs = [Paragraph(v, style_kpi_valeur) for v, _ in kpis]
    ligne_libelles = [Paragraph(l.replace("\n", "<br/>"), style_kpi_libelle) for _, l in kpis]
    t_kpi = Table([ligne_valeurs, ligne_libelles], colWidths=[3.6 * cm] * 5)
    style_kpi = TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _COULEUR_LIGNE_ALT),
        ("BOX", (0, 0), (-1, -1), 0.5, _COULEUR_BORD),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("TOPPADDING", (0, 1), (-1, 1), 2),
    ])
    for i, couleur in enumerate(_KPI_COULEURS):
        style_kpi.add("LINEABOVE", (i, 0), (i, 0), 2.5, couleur)
        style_kpi.add("TEXTCOLOR", (i, 0), (i, 0), couleur)
        if i > 0:
            style_kpi.add("LINEBEFORE", (i, 0), (i, -1), 0.5, _COULEUR_BORD)
    t_kpi.setStyle(style_kpi)
    elements.append(t_kpi)

    # ---- Documents par type ----
    elements.append(Paragraph("Documents administratifs par type", style_section))
    data = [["Type de document", "Total", "En cours", "Validés", "Refusés", "Montant validé"]]
    for ligne in d["par_type"]:
        if ligne["total"] == 0:
            continue
        data.append([
            ligne["type_document_libelle"], str(ligne["total"]), str(ligne["en_cours"]),
            str(ligne["valides"]), str(ligne["refuses"]), _fmt_montant(ligne["montant_valide"], 2),
        ])
    if len(data) == 1:
        data.append(["Aucun document sur la période", "", "", "", "", ""])
    data.append(["TOTAL", str(d["total_documents"]), "", "", "", _fmt_montant(d["montant_total_valide"], 2)])

    t_docs = Table(data, colWidths=[5.6 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm, 1.9 * cm, 3.3 * cm])
    style_docs = TableStyle(_entete_tableau() + [
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, _COULEUR_ENTETE),
        ("BACKGROUND", (0, -1), (-1, -1), colors.white),
    ])
    t_docs.setStyle(style_docs)
    elements.append(t_docs)

    # ---- Contrats & Stocks côte à côte ----
    elements.append(Paragraph("Contrats", style_section))
    t_contrats = Table(
        [["Actifs", "Expirés", "Résiliés", "Montant engagé", "Échéances < 30j"],
         [str(c["actifs"]), str(c["expires"]), str(c["resilies"]), _fmt_montant(c["montant_engage"], 2), str(c["echeances_proches_30j"])]],
        colWidths=[3.3 * cm] * 3 + [3.5 * cm, 3.7 * cm],
    )
    t_contrats.setStyle(TableStyle(_entete_tableau() + [("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    elements.append(t_contrats)

    elements.append(Paragraph("Stocks (mouvements de la période)", style_section))
    t_stocks = Table(
        [["Mouvements", "Quantité entrées", "Quantité sorties", "Articles en alerte"],
         [str(s["mouvements_total"]), str(s["quantite_entrees"]), str(s["quantite_sorties"]), str(s["articles_en_alerte"])]],
        colWidths=[3.4 * cm, 4 * cm, 4 * cm, 4 * cm],
    )
    t_stocks.setStyle(TableStyle(_entete_tableau() + [("ALIGN", (0, 0), (-1, -1), "CENTER")]))
    elements.append(t_stocks)

    # ---- Répartition par filiale (groupe entier uniquement) ----
    if rapport.get("repartition_par_filiale"):
        elements.append(Paragraph("Répartition par filiale — montant validé", style_section))
        repartition = sorted(
            rapport["repartition_par_filiale"], key=lambda l: float(l["montant_valide"]), reverse=True,
        )
        data_rep = [["Filiale", "Montant validé"]] + [
            [l["filiale"], _fmt_montant(l["montant_valide"], 2)] for l in repartition
        ]
        t_rep = Table(data_rep, colWidths=[9 * cm, 6 * cm])
        t_rep.setStyle(TableStyle(_entete_tableau() + [
            ("ALIGN", (1, 0), (1, -1), "RIGHT"), ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ]))
        elements.append(t_rep)

    doc.build(elements, onFirstPage=_pied_page, onLaterPages=_pied_page)
    tampon.seek(0)
    return tampon.getvalue()
