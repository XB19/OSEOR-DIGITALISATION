"""
Rapports administratifs : consolidation et restitution comptable /
administrative — synthèse des documents (Moyens Généraux), contrats et
mouvements de stock sur une période donnée, par filiale ou pour tout le
groupe. Purement en lecture : aucune donnée propre, tout est dérivé des
autres modules (documents, contrats, stocks).
"""

import csv
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import GereLesRapports
from applications.filiales.models import Filiale
from applications.documents.models import Document, TypeDocument
from applications.contrats.models import Contrat
from applications.stocks.models import Article, MouvementStock


def _parse_date(valeur):
    if not valeur:
        return None
    try:
        return date.fromisoformat(valeur)
    except ValueError:
        return None


def _plage_dates(request):
    aujourdhui = timezone.localdate()
    debut_mois = aujourdhui.replace(day=1)
    date_debut = _parse_date(request.query_params.get("date_debut")) or debut_mois
    date_fin = _parse_date(request.query_params.get("date_fin")) or aujourdhui
    return date_debut, date_fin


def _filiale_cible(request):
    """
    Le Comptable ne consulte que sa propre filiale (jamais modifiable via
    l'URL) ; le Directeur et l'Administrateur peuvent choisir une filiale ou
    consulter le groupe entier (`filiale` absent = toutes les filiales).
    """
    u = request.user
    if u.role == "COMPTABLE":
        return u.filiale
    filiale_id = request.query_params.get("filiale")
    if filiale_id:
        return Filiale.objects.filter(pk=filiale_id).first()
    return None


def _consolidation_documents(filiale, date_debut, date_fin):
    qs = Document.objects.filter(date_creation__date__gte=date_debut, date_creation__date__lte=date_fin)
    if filiale:
        qs = qs.filter(filiale=filiale)

    par_type = []
    montant_total_valide = Decimal("0")
    for type_doc, libelle in TypeDocument.choices:
        sous_qs = qs.filter(type_document=type_doc)
        montant_valide = sous_qs.filter(statut=Document.Statut.VALIDE).aggregate(s=Sum("montant_total"))["s"] or Decimal("0")
        montant_total_valide += montant_valide
        par_type.append({
            "type_document": type_doc,
            "type_document_libelle": libelle,
            "total": sous_qs.count(),
            "en_cours": sous_qs.filter(statut=Document.Statut.EN_COURS).count(),
            "valides": sous_qs.filter(statut=Document.Statut.VALIDE).count(),
            "refuses": sous_qs.filter(statut=Document.Statut.REFUSE).count(),
            "montant_valide": str(montant_valide),
        })

    return {
        "par_type": par_type,
        "total_documents": qs.count(),
        "montant_total_valide": str(montant_total_valide),
    }


def _consolidation_contrats(filiale):
    qs = Contrat.objects.all()
    if filiale:
        qs = qs.filter(filiale=filiale)

    montant_engage = qs.filter(statut=Contrat.Statut.ACTIF).aggregate(s=Sum("montant"))["s"] or Decimal("0")
    echeances_proches = sum(
        1 for c in qs.filter(statut=Contrat.Statut.ACTIF, date_echeance__isnull=False)
        if c.jours_avant_echeance is not None and 0 <= c.jours_avant_echeance <= 30
    )

    return {
        "actifs": qs.filter(statut=Contrat.Statut.ACTIF).count(),
        "expires": qs.filter(statut=Contrat.Statut.EXPIRE).count(),
        "resilies": qs.filter(statut=Contrat.Statut.RESILIE).count(),
        "montant_engage": str(montant_engage),
        "echeances_proches_30j": echeances_proches,
    }


def _consolidation_stocks(filiale, date_debut, date_fin):
    qs = MouvementStock.objects.filter(date_creation__date__gte=date_debut, date_creation__date__lte=date_fin)
    if filiale:
        qs = qs.filter(article__filiale=filiale)

    entrees = qs.filter(type_mouvement=MouvementStock.Type.ENTREE).aggregate(q=Sum("quantite"))["q"] or 0
    sorties = qs.filter(type_mouvement=MouvementStock.Type.SORTIE).aggregate(q=Sum("quantite"))["q"] or 0

    articles_qs = Article.objects.filter(actif=True)
    if filiale:
        articles_qs = articles_qs.filter(filiale=filiale)
    en_alerte = sum(1 for a in articles_qs if a.en_alerte)

    return {
        "mouvements_total": qs.count(),
        "quantite_entrees": entrees,
        "quantite_sorties": sorties,
        "articles_en_alerte": en_alerte,
    }


def _repartition_par_filiale(date_debut, date_fin):
    """Groupe entier uniquement : montant validé par filiale, pour comparer d'un coup d'œil."""
    resultats = []
    for f in Filiale.objects.filter(active=True):
        montant = Document.objects.filter(
            filiale=f, statut=Document.Statut.VALIDE,
            date_creation__date__gte=date_debut, date_creation__date__lte=date_fin,
        ).aggregate(s=Sum("montant_total"))["s"] or Decimal("0")
        resultats.append({"filiale": f.nom, "filiale_id": f.id, "montant_valide": str(montant)})
    return resultats


def _construire_rapport(request):
    u = request.user
    date_debut, date_fin = _plage_dates(request)
    filiale = _filiale_cible(request)

    rapport = {
        "periode": {"date_debut": date_debut.isoformat(), "date_fin": date_fin.isoformat()},
        "filiale": filiale.nom if filiale else "Groupe (toutes filiales)",
        "filiale_id": filiale.id if filiale else None,
        "documents": _consolidation_documents(filiale, date_debut, date_fin),
        "contrats": _consolidation_contrats(filiale),
        "stocks": _consolidation_stocks(filiale, date_debut, date_fin),
    }
    if filiale is None and u.role in ("ADMINISTRATEUR", "DIRECTEUR"):
        rapport["repartition_par_filiale"] = _repartition_par_filiale(date_debut, date_fin)

    return rapport, date_debut, date_fin


class RapportAdministratifView(APIView):
    """Consolidation comptable / administrative — documents, contrats, stocks."""

    permission_classes = [IsAuthenticated, GereLesRapports]

    def get(self, request):
        rapport, _, _ = _construire_rapport(request)
        return Response(rapport)


class RapportAdministratifExportView(APIView):
    """Même consolidation que RapportAdministratifView, restituée en CSV téléchargeable."""

    permission_classes = [IsAuthenticated, GereLesRapports]

    def get(self, request):
        rapport, date_debut, date_fin = _construire_rapport(request)

        reponse = HttpResponse(content_type="text/csv")
        reponse["Content-Disposition"] = f'attachment; filename="rapport_administratif_{date_debut}_{date_fin}.csv"'
        reponse.write("﻿")  # BOM : accents lisibles à l'ouverture dans Excel

        writer = csv.writer(reponse)
        writer.writerow(["Rapport administratif", f"Du {date_debut} au {date_fin}", rapport["filiale"]])
        writer.writerow([])

        writer.writerow(["Documents", "Total", "En cours", "Validés", "Refusés", "Montant validé"])
        for ligne in rapport["documents"]["par_type"]:
            writer.writerow([
                ligne["type_document_libelle"], ligne["total"], ligne["en_cours"],
                ligne["valides"], ligne["refuses"], ligne["montant_valide"],
            ])
        writer.writerow([
            "TOTAL", rapport["documents"]["total_documents"], "", "", "",
            rapport["documents"]["montant_total_valide"],
        ])
        writer.writerow([])

        c = rapport["contrats"]
        writer.writerow(["Contrats", "Actifs", "Expirés", "Résiliés", "Montant engagé", "Échéances < 30j"])
        writer.writerow(["", c["actifs"], c["expires"], c["resilies"], c["montant_engage"], c["echeances_proches_30j"]])
        writer.writerow([])

        s = rapport["stocks"]
        writer.writerow(["Stocks", "Mouvements", "Quantité entrées", "Quantité sorties", "Articles en alerte"])
        writer.writerow(["", s["mouvements_total"], s["quantite_entrees"], s["quantite_sorties"], s["articles_en_alerte"]])

        if "repartition_par_filiale" in rapport:
            writer.writerow([])
            writer.writerow(["Répartition par filiale", "Montant validé"])
            for ligne in rapport["repartition_par_filiale"]:
                writer.writerow([ligne["filiale"], ligne["montant_valide"]])

        return reponse
