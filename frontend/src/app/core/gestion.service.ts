import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/**
 * Caisses, bons de sortie et procédures disciplinaires.
 *
 * Séparé de `vie-interne.service.ts` (congés, événements, galerie) : ce
 * sont des domaines à part, l'un financier, l'autre RH, et les regrouper
 * ferait un service que personne ne lit en entier.
 */

export interface Paginated<T> {
  count: number;
  results: T[];
}

function parametres(source: Record<string, unknown> = {}): Record<string, string> {
  const sortie: Record<string, string> = {};
  for (const [cle, valeur] of Object.entries(source)) {
    if (valeur !== undefined && valeur !== null && valeur !== '') {
      sortie[cle] = String(valeur);
    }
  }
  return sortie;
}

// ---------------------------------------------------------------- Caisse

export interface Caisse {
  id: number;
  nom: string;
  code: string;
  filiale: number;
  filiale_nom: string;
  detenteur: number | null;
  detenteur_nom: string | null;
  description: string;
  active: boolean;
  solde: string;
  date_creation: string;
}

export interface MouvementCaisse {
  id: number;
  caisse: number;
  type_mouvement: string;
  type_libelle: string;
  montant: string;
  justificatif: string | null;
  reference: string;
  motif: string;
  bon_sortie: number | null;
  bon_reference: string | null;
  cree_par_nom: string;
  date_operation: string;
}

export interface BonSortie {
  id: number;
  reference: string;
  caisse: number;
  caisse_nom: string;
  demandeur: number;
  demandeur_nom: string;
  destinataire: number | null;
  destinataire_nom: string | null;
  objet: string;
  montant: string;
  type_depense: string;
  type_libelle: string;
  moyen_transport: string;
  moyen_libelle: string;
  exige_justificatif: boolean;
  justificatif: string | null;
  statut: string;
  statut_libelle: string;
  motif_decision: string;
  montant_paye: string;
  montant_rendu: string;
  montant_consomme: string;
  document: number | null;
  date_creation: string;
}

export interface ReglesBon {
  seuil_direction: string;
  roles_sous_seuil: string[];
  roles_au_dessus: string[];
  moyens_avec_justificatif: string[];
}

@Injectable({ providedIn: 'root' })
export class CaisseService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  caisses(filtres: Record<string, unknown> = {}): Observable<Paginated<Caisse>> {
    return this.http.get<Paginated<Caisse>>(
      `${this.api}/caisses/`, { params: parametres(filtres) });
  }

  registre(caisseId: number): Observable<MouvementCaisse[]> {
    return this.http.get<MouvementCaisse[]>(
      `${this.api}/caisses/${caisseId}/registre/`);
  }

  /** Une alimentation exige une preuve : justificatif ou référence. */
  alimenter(caisseId: number, donnees: {
    montant: string; reference?: string; motif?: string; justificatif?: File | null;
  }): Observable<MouvementCaisse> {
    const corps = new FormData();
    corps.append('montant', donnees.montant);
    if (donnees.reference) corps.append('reference', donnees.reference);
    if (donnees.motif) corps.append('motif', donnees.motif);
    if (donnees.justificatif) corps.append('justificatif', donnees.justificatif);
    return this.http.post<MouvementCaisse>(
      `${this.api}/caisses/${caisseId}/alimenter/`, corps);
  }

  corriger(caisseId: number, montant: string, motif: string): Observable<MouvementCaisse> {
    return this.http.post<MouvementCaisse>(
      `${this.api}/caisses/${caisseId}/corriger/`, { montant, motif });
  }

  bons(filtres: Record<string, unknown> = {}): Observable<Paginated<BonSortie>> {
    return this.http.get<Paginated<BonSortie>>(
      `${this.api}/bons-sortie/`, { params: parametres(filtres) });
  }

  aAutoriser(): Observable<BonSortie[]> {
    return this.http.get<BonSortie[]>(`${this.api}/bons-sortie/a_autoriser/`);
  }

  regles(): Observable<ReglesBon> {
    return this.http.get<ReglesBon>(`${this.api}/bons-sortie/regles/`);
  }

  deposerBon(donnees: {
    caisse: number; objet: string; montant: string; type_depense: string;
    moyen_transport?: string; destinataire?: number | null; justificatif?: File | null;
  }): Observable<BonSortie> {
    const corps = new FormData();
    corps.append('caisse', String(donnees.caisse));
    corps.append('objet', donnees.objet);
    corps.append('montant', donnees.montant);
    corps.append('type_depense', donnees.type_depense);
    if (donnees.moyen_transport) corps.append('moyen_transport', donnees.moyen_transport);
    if (donnees.destinataire) corps.append('destinataire', String(donnees.destinataire));
    if (donnees.justificatif) corps.append('justificatif', donnees.justificatif);
    return this.http.post<BonSortie>(`${this.api}/bons-sortie/`, corps);
  }

  deciderBon(id: number, autorise: boolean, motif = ''): Observable<BonSortie> {
    return this.http.post<BonSortie>(
      `${this.api}/bons-sortie/${id}/decider/`, { autorise, motif });
  }

  payerBon(id: number): Observable<BonSortie> {
    return this.http.post<BonSortie>(`${this.api}/bons-sortie/${id}/payer/`, {});
  }

  rendreMonnaie(id: number, montant: string, motif = ''): Observable<BonSortie> {
    return this.http.post<BonSortie>(
      `${this.api}/bons-sortie/${id}/rendre/`, { montant, motif });
  }

  urlPdf(id: number): string {
    return `${this.api}/bons-sortie/${id}/pdf/`;
  }
}

// ------------------------------------------------------------ Discipline

export interface Explication {
  id: number;
  mode: string;
  mode_libelle: string;
  contenu: string;
  piece_jointe: string | null;
  delegue_present: boolean;
  consignee_par_nom: string;
  date_explication: string;
}

export interface Sanction {
  id: number;
  type_sanction: string;
  type_libelle: string;
  duree_jours: number | null;
  motif: string;
  prononcee_par_nom: string;
  date_prononce: string;
  date_notification: string | null;
  date_inspection_travail: string | null;
  formalites_completes: boolean;
}

export interface ProcedureDisciplinaire {
  id: number;
  reference: string;
  salarie: number;
  salarie_nom: string;
  filiale_nom: string;
  faits: string;
  date_faits: string;
  date_preuve: string;
  qualification: string;
  qualification_libelle: string;
  faute_lourde_invoquee: string;
  statut: string;
  statut_libelle: string;
  mise_a_pied_conservatoire: boolean;
  date_mise_a_pied: string | null;
  date_limite_sanction: string;
  delai_depasse: boolean;
  explications_recueillies: boolean;
  explications: Explication[];
  sanction: Sanction | null;
  ouverte_par_nom: string;
  motif_classement: string;
  date_ouverture: string;
}

export interface BaremeSanction {
  code: string;
  libelle: string;
  rang: number;
  jours_min: number | null;
  jours_max: number | null;
  faute_lourde_requise: boolean;
}

export interface BaremeDisciplinaire {
  delai_mois: number;
  sanctions: BaremeSanction[];
  fautes_lourdes: { code: string; libelle: string }[];
}

@Injectable({ providedIn: 'root' })
export class DisciplineService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;
  private base = `${environment.apiUrl}/procedures-disciplinaires`;

  liste(filtres: Record<string, unknown> = {}): Observable<Paginated<ProcedureDisciplinaire>> {
    return this.http.get<Paginated<ProcedureDisciplinaire>>(
      `${this.base}/`, { params: parametres(filtres) });
  }

  detail(id: number): Observable<ProcedureDisciplinaire> {
    return this.http.get<ProcedureDisciplinaire>(`${this.base}/${id}/`);
  }

  /** Barème de l'article 58 : bornes de durée et fautes lourdes. */
  bareme(): Observable<BaremeDisciplinaire> {
    return this.http.get<BaremeDisciplinaire>(`${this.base}/bareme/`);
  }

  ouvrir(donnees: {
    salarie: number; faits: string; date_faits: string; date_preuve: string;
    qualification?: string; faute_lourde_invoquee?: string;
    mise_a_pied_conservatoire?: boolean;
  }): Observable<ProcedureDisciplinaire> {
    return this.http.post<ProcedureDisciplinaire>(`${this.base}/`, donnees);
  }

  demanderExplications(id: number): Observable<ProcedureDisciplinaire> {
    return this.http.post<ProcedureDisciplinaire>(
      `${this.base}/${id}/demander_explications/`, {});
  }

  expliquer(id: number, donnees: {
    mode: string; contenu?: string; delegue_present?: boolean; piece_jointe?: File | null;
  }): Observable<Explication> {
    const corps = new FormData();
    corps.append('mode', donnees.mode);
    if (donnees.contenu) corps.append('contenu', donnees.contenu);
    corps.append('delegue_present', String(!!donnees.delegue_present));
    if (donnees.piece_jointe) corps.append('piece_jointe', donnees.piece_jointe);
    return this.http.post<Explication>(`${this.base}/${id}/expliquer/`, corps);
  }

  prononcer(id: number, donnees: {
    type_sanction: string; motif: string; duree_jours?: number | null;
  }): Observable<Sanction> {
    return this.http.post<Sanction>(`${this.base}/${id}/prononcer/`, donnees);
  }

  formalites(id: number, donnees: {
    date_notification?: string | null; date_inspection_travail?: string | null;
  }): Observable<Sanction> {
    return this.http.post<Sanction>(`${this.base}/${id}/formalites/`, donnees);
  }

  classer(id: number, motif: string): Observable<ProcedureDisciplinaire> {
    return this.http.post<ProcedureDisciplinaire>(
      `${this.base}/${id}/classer/`, { motif });
  }
}

// ------------------------------------------------- Dates de naissance (admin)

export interface LigneDateNaissance {
  id: number;
  nom_complet: string;
  filiale: string | null;
  date_naissance: string | null;
}

@Injectable({ providedIn: 'root' })
export class DatesNaissanceService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  liste(): Observable<LigneDateNaissance[]> {
    return this.http.get<LigneDateNaissance[]>(
      `${this.api}/utilisateurs/dates_naissance/`);
  }

  enregistrer(dates: Record<string, string | null>): Observable<{ mis_a_jour: number }> {
    return this.http.post<{ mis_a_jour: number }>(
      `${this.api}/utilisateurs/dates_naissance/`, { dates });
  }
}
