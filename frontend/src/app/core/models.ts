// Modèles partagés (alignés sur l'API DRF OSEOR).

export type Role = 'ADMINISTRATEUR' | 'DIRECTEUR' | 'SECRETAIRE'
  | 'CHEF_SERVICE' | 'COMPTABLE' | 'RH' | 'EMPLOYE';

export interface Utilisateur {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  nom_complet: string;
  email: string;
  telephone: string;
  role: Role;
  role_libelle: string;
  filiale: number | null;
  filiale_nom: string | null;
  actif: boolean;
  source_auth?: 'SSO' | 'LOCAL';
  permissions?: {
    est_administrateur: boolean;
    est_secretaire: boolean;
    est_directeur: boolean;
    est_employe: boolean;
  };
}

export interface Filiale {
  id: number;
  nom: string;
  code: string;
  description?: string;
  email?: string;
  telephone?: string;
  adresse?: string;
  active: boolean;
}

export interface Salle {
  id: number;
  nom: string;
  filiale: number;
  filiale_nom?: string;
  description?: string;
  capacite: number;
  equipements: string[];
  photo?: string | null;
  active: boolean;
}

export interface Equipement {
  code: string;
  libelle: string;
}

export type StatutReservation =
  'BROUILLON' | 'EN_ATTENTE' | 'VALIDEE' | 'REFUSEE'
  | 'ANNULEE' | 'DEPLACEE' | 'TERMINEE';

export interface Participant {
  id?: number;
  nom: string;
  prenom?: string;
  nom_complet?: string;
  email?: string;
  telephone?: string;
  societe?: string;
  type_participant: 'INTERNE' | 'EXTERNE';
  utilisateur?: number | null;
}

export interface Reservation {
  id: number;
  demandeur?: number;
  demandeur_nom?: string;
  nom_reservant: string;
  telephone?: string;
  motif?: string;
  salle: number;
  salle_nom?: string;
  filiale_nom?: string;
  date_reunion: string;
  heure_debut: string;
  heure_fin: string;
  precisions?: string;
  statut: StatutReservation;
  statut_libelle?: string;
  motif_refus?: string;
  motif_annulation?: string;
  serie?: number | null;
  serie_frequence?: string | null;
  serie_date_debut?: string | null;
  serie_date_fin?: string | null;
  participants?: Participant[];
  date_creation?: string;
}

export interface DisponibiliteResultat {
  disponible: boolean;
  conflits: Reservation[];
}

export type StatutAudience =
  'SAISIE' | 'ENVOYEE_DG' | 'RENVOYEE_SECRETAIRE'
  | 'VALIDEE_DG' | 'CONFIRMEE' | 'ANNULEE' | 'TERMINEE';

export interface EchangeAudience {
  id: number;
  auteur: number;
  auteur_nom: string;
  commentaire: string;
  date_creation: string;
}

export interface Delegation {
  id: number;
  audience: number;
  delegue: number;
  delegue_nom: string;
  delegue_email: string;
  commentaire: string;
  statut: 'PROPOSEE' | 'PRISE_EN_COMPTE';
  statut_libelle: string;
  date_proposition: string;
  date_prise_en_compte: string | null;
}

export interface Audience {
  id: number;
  nom: string;
  prenom?: string;
  nom_complet?: string;
  profession?: string;
  contact?: string;
  objet_visite: string;
  secretaire?: number;
  secretaire_nom?: string;
  dg: number;
  dg_nom?: string;
  statut: StatutAudience;
  statut_libelle?: string;
  date_souhaitee?: string | null;
  heure_debut?: string | null;
  heure_fin?: string | null;
  salle?: number | null;
  salle_nom?: string | null;
  lieu?: string;
  reservation?: number | null;
  echanges?: EchangeAudience[];
  delegations?: Delegation[];
  date_creation?: string;
}

export interface NotificationItem {
  id: number;
  titre: string;
  message: string;
  type: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  lu: boolean;
  objet_type: string;
  objet_id: number | null;
  date_creation: string;
}

export interface ParametresLDAP {
  server_uri: string;
  domaine: string;
  base_dn: string;
  bind_dn: string;
  mot_de_passe_defini: boolean;
  configure: boolean;
  date_modification: string;
}

export type TypeDocumentAdministratif =
  'FICHE_BESOIN' | 'DEMANDE_ACHAT' | 'FICHE_TRANSPORT' | 'BON_SORTIE_CAISSE';

export interface ColonneDocument {
  cle: string;
  libelle: string;
}

export interface EtapeVisa {
  cle: string;
  libelle: string;
  role?: string;
}

export interface ConfigurationDocument {
  filiale: number;
  type_document: TypeDocumentAdministratif;
  type_document_libelle: string;
  colonnes: ColonneDocument[];
  visas: EtapeVisa[];
}

export interface HistoriqueVisa {
  etape: number;
  cle: string;
  libelle: string;
  utilisateur_id: number;
  utilisateur_nom: string;
  decision: 'VALIDE' | 'REFUSE';
  commentaire: string;
  date: string;
  a_une_signature: boolean;
}

export interface DocumentAdministratif {
  id: number;
  numero: string;
  type_document: TypeDocumentAdministratif;
  type_document_libelle: string;
  filiale: number;
  filiale_nom: string;
  demandeur: number;
  demandeur_nom: string;
  champs_entete: Record<string, any>;
  lignes: Record<string, any>[];
  montant_total: string;
  statut: 'EN_COURS' | 'VALIDE' | 'REFUSE';
  statut_libelle: string;
  etape_visa_courante: number;
  historique_visas: HistoriqueVisa[];
  motif_rejet: string;
  visa_courant: EtapeVisa | null;
  peut_viser: boolean;
  date_creation: string;
  date_modification: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
