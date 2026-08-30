import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

/**
 * Services des modules « vie interne » : congés, événements, galerie,
 * prestations.
 *
 * Volontairement à part d'`api.service.ts` : ce dernier concentre déjà les
 * réservations, audiences et documents, et plusieurs personnes y
 * travaillent en même temps. Des services séparés par domaine évitent les
 * conflits et restent la pratique Angular recommandée.
 */

export interface Paginated<T> {
  count: number;
  results: T[];
}

/**
 * Construit les paramètres d'URL en écartant ce qui est vide.
 *
 * `HttpClient` refuse un objet dont une valeur peut être `undefined` : il
 * faut donc filtrer AVANT de le lui passer, et non lui tendre un objet
 * partiellement rempli.
 */
function parametres(source: Record<string, unknown> = {}): Record<string, string> {
  const sortie: Record<string, string> = {};
  for (const [cle, valeur] of Object.entries(source)) {
    if (valeur !== undefined && valeur !== null && valeur !== '') {
      sortie[cle] = String(valeur);
    }
  }
  return sortie;
}

// ---------------------------------------------------------------- Congés

export interface SoldeConge {
  annee: number;
  /** Cumul de toutes les années : le droit réel du salarié. */
  acquis_total: string;
  pris_total: string;
  solde: string;
  reserves: string;
  disponible: string;
  /** Détail de l'année en cours. */
  acquis: string;
  pris: string;
}

export interface MotifPermission {
  code: string;
  libelle: string;
  jours: number;
  justificatif: string;
  anciennete_requise: boolean;
  plafond_annuel: number | null;
}

export interface DemandeConge {
  id: number;
  utilisateur: number;
  utilisateur_nom: string;
  type_conge: string;
  type_libelle: string;
  motif_permission: string;
  motif_permission_libelle: string;
  date_evenement: string | null;
  justificatif: string | null;
  justificatif_attendu: string;
  date_limite_justificatif: string | null;
  justificatif_en_retard: boolean;
  date_debut: string;
  date_fin: string;
  jours_ouvres: number;
  motif: string;
  statut: string;
  statut_libelle: string;
  valideur_nom: string | null;
  date_decision: string | null;
  motif_decision: string;
  date_creation: string;
  /** Parcours après validation (report, rappel, reprise). */
  date_debut_initiale: string | null;
  motif_report: string;
  date_rappel: string | null;
  motif_rappel: string;
  date_reprise: string | null;
}

export interface MouvementConge {
  id: number;
  annee: number;
  type_mouvement: string;
  type_libelle: string;
  jours: string;
  date_effet: string;
  motif: string;
}

@Injectable({ providedIn: 'root' })
export class CongesService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  mesDemandes(filtres: Record<string, unknown> = {}): Observable<Paginated<DemandeConge>> {
    return this.http.get<Paginated<DemandeConge>>(
      `${this.api}/conges/`, { params: parametres(filtres) });
  }

  monSolde(annee?: number): Observable<SoldeConge> {
    return this.http.get<SoldeConge>(
      `${this.api}/conges/mon_solde/`, { params: parametres({ annee }) });
  }

  monRegistre(annee?: number): Observable<MouvementConge[]> {
    return this.http.get<MouvementConge[]>(
      `${this.api}/conges/mon_registre/`, { params: parametres({ annee }) });
  }

  aValider(): Observable<DemandeConge[]> {
    return this.http.get<DemandeConge[]>(`${this.api}/conges/a_valider/`);
  }

  /** Barème de l'article 45 de la Convention Collective du Togo. */
  baremePermissions(): Observable<MotifPermission[]> {
    return this.http.get<MotifPermission[]>(`${this.api}/conges/bareme_permissions/`);
  }

  deposer(demande: {
    type_conge: string;
    date_debut: string;
    date_fin: string;
    motif?: string;
    motif_permission?: string;
    date_evenement?: string | null;
  }): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(`${this.api}/conges/`, demande);
  }

  decider(id: number, approuvee: boolean, motif = ''): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(`${this.api}/conges/${id}/decider/`, { approuvee, motif });
  }

  annuler(id: number, motif = ''): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(`${this.api}/conges/${id}/annuler/`, { motif });
  }

  /** Décale le départ — plafonné à trois mois par l'article 44 de la CCIT. */
  reporter(id: number, dateDebut: string, motif: string): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(
      `${this.api}/conges/${id}/reporter/`, { date_debut: dateDebut, motif });
  }

  /** Rappelle un salarié en service pendant son congé. */
  rappeler(id: number, motif: string, jour?: string): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(
      `${this.api}/conges/${id}/rappeler/`, { motif, jour: jour || null });
  }

  /** Reprise du congé : les jours travaillés sont rendus (article 44d). */
  reprendre(id: number, jour?: string): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(
      `${this.api}/conges/${id}/reprendre/`, { jour: jour || null });
  }

  /** Renonce au reliquat ; les jours non pris sont recrédités. */
  ecourter(id: number, jour?: string): Observable<DemandeConge> {
    return this.http.post<DemandeConge>(
      `${this.api}/conges/${id}/ecourter/`, { jour: jour || null });
  }

  deposerJustificatif(id: number, fichier: File): Observable<DemandeConge> {
    const corps = new FormData();
    corps.append('justificatif', fichier);
    return this.http.post<DemandeConge>(`${this.api}/conges/${id}/justificatif/`, corps);
  }
}

// ------------------------------------------------------------ Événements

export interface Evenement {
  id: number;
  titre: string;
  type_evenement: string;
  type_libelle: string;
  description: string;
  date_debut: string;
  date_fin: string;
  journee_entiere: boolean;
  lieu: string;
  filiale_nom: string;
  service_nom: string | null;
  visibilite: string;
  visibilite_libelle: string;
  photo: string | null;
  createur: number;
  createur_nom: string;
  annule: boolean;
}

export interface Anniversaire {
  type: string;
  titre: string;
  date: string;
  utilisateur_id: number;
}

export interface Calendrier {
  debut: string;
  fin: string;
  evenements: Evenement[];
  anniversaires: Anniversaire[];
}

@Injectable({ providedIn: 'root' })
export class EvenementsService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  liste(filtres: Record<string, unknown> = {}): Observable<Paginated<Evenement>> {
    return this.http.get<Paginated<Evenement>>(
      `${this.api}/evenements/`, { params: parametres(filtres) });
  }

  calendrier(debut?: string, fin?: string): Observable<Calendrier> {
    return this.http.get<Calendrier>(
      `${this.api}/evenements/calendrier/`, { params: parametres({ debut, fin }) });
  }

  creer(e: Partial<Evenement>): Observable<Evenement> {
    return this.http.post<Evenement>(`${this.api}/evenements/`, e);
  }

  modifier(id: number, e: Partial<Evenement>): Observable<Evenement> {
    return this.http.patch<Evenement>(`${this.api}/evenements/${id}/`, e);
  }

  supprimer(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/evenements/${id}/`);
  }
}

// --------------------------------------------------------------- Galerie

export interface Album {
  id: number;
  titre: string;
  description: string;
  filiale_nom: string;
  service_nom: string | null;
  evenement: number | null;
  evenement_titre: string | null;
  visibilite: string;
  visibilite_libelle: string;
  date_evenement: string | null;
  createur: number;
  createur_nom: string;
  nb_photos: number;
  couverture: string | null;
  date_creation: string;
}

export interface Photo {
  id: number;
  album: number;
  image: string;
  miniature: string | null;
  legende: string;
  largeur: number;
  hauteur: number;
  televersee_par: number;
  televersee_par_nom: string;
  date_creation: string;
}

@Injectable({ providedIn: 'root' })
export class GalerieService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  albums(filtres: Record<string, unknown> = {}): Observable<Paginated<Album>> {
    return this.http.get<Paginated<Album>>(
      `${this.api}/albums/`, { params: parametres(filtres) });
  }

  album(id: number): Observable<Album> {
    return this.http.get<Album>(`${this.api}/albums/${id}/`);
  }

  creerAlbum(a: Partial<Album>): Observable<Album> {
    return this.http.post<Album>(`${this.api}/albums/`, a);
  }

  supprimerAlbum(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/albums/${id}/`);
  }

  photos(albumId?: number): Observable<Paginated<Photo>> {
    return this.http.get<Paginated<Photo>>(
      `${this.api}/photos/`, { params: parametres({ album: albumId }) });
  }

  televerser(albumId: number, fichier: File, legende = ''): Observable<Photo> {
    const corps = new FormData();
    corps.append('album', String(albumId));
    corps.append('image', fichier);
    if (legende) corps.append('legende', legende);
    return this.http.post<Photo>(`${this.api}/photos/`, corps);
  }

  supprimerPhoto(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/photos/${id}/`);
  }
}

// ----------------------------------------------------------- Prestations

export interface Jalon {
  id: number;
  prestation: number;
  intitule: string;
  date_prevue: string;
  date_realisation: string | null;
  realise: boolean;
  commentaire: string;
}

export interface Avancement {
  jalons: number;
  realises: number;
  pourcentage: number;
  prochain: string | null;
  jalons_en_retard: number;
}

export interface Prestation {
  id: number;
  reference: string;
  intitule: string;
  client: string;
  description: string;
  filiale_nom: string;
  service: number;
  service_nom: string;
  responsable: number;
  responsable_nom: string;
  date_debut: string;
  date_fin_prevue: string;
  date_fin_reelle: string | null;
  montant: string;
  statut: string;
  statut_libelle: string;
  en_retard: boolean;
  avancement: Avancement | null;
  jalons: Jalon[];
}

@Injectable({ providedIn: 'root' })
export class PrestationsService {
  private http = inject(HttpClient);
  private api = environment.apiUrl;

  liste(filtres: Record<string, unknown> = {}): Observable<Paginated<Prestation>> {
    return this.http.get<Paginated<Prestation>>(
      `${this.api}/prestations/`, { params: parametres(filtres) });
  }

  tableauDeBord(): Observable<{ total: number; par_statut: Record<string, number>; en_retard: Prestation[] }> {
    return this.http.get<any>(`${this.api}/prestations/tableau_de_bord/`);
  }

  creer(p: Partial<Prestation>): Observable<Prestation> {
    return this.http.post<Prestation>(`${this.api}/prestations/`, p);
  }

  cloturer(id: number): Observable<Prestation> {
    return this.http.post<Prestation>(`${this.api}/prestations/${id}/cloturer/`, {});
  }

  ajouterJalon(j: Partial<Jalon>): Observable<Jalon> {
    return this.http.post<Jalon>(`${this.api}/jalons/`, j);
  }

  realiserJalon(id: number): Observable<Jalon> {
    return this.http.post<Jalon>(`${this.api}/jalons/${id}/realiser/`, {});
  }
}
