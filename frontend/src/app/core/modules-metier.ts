// Registre des modules « Moyens Généraux » (au-delà de la réservation de
// salles et des audiences). Source unique utilisée par la navigation, le
// tableau de bord et les routes — chaque module sera implémenté un à un ;
// en attendant, sa route pointe vers EnConstructionComponent.
//
// `roles` absent = visible par tous les utilisateurs connectés (ex. Fiche
// de besoin). Le Directeur Général et l'Administrateur voient tout, pour
// pouvoir approuver/décliner/observer (signature scannée).

export interface ModuleMetier {
  lien: string;
  libelle: string;
  icone: string;
  roles?: string[];
}

export const MODULES_MOYENS_GENERAUX: ModuleMetier[] = [
  { lien: '/fiche-besoin', libelle: 'Fiche de besoin', icone: 'send' },
  { lien: '/demandes-achat', libelle: "Demandes d'achat", icone: 'cart' },
  {
    lien: '/factures', libelle: 'Factures', icone: 'receipt',
    roles: ['SECRETAIRE', 'COMPTABLE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/bons-commande', libelle: 'Bons de commande', icone: 'cart',
    // CHEF_SERVICE inclus : c'est lui qui vise l'étape intermédiaire du
    // circuit de validation (cf. seed_config_documents.py).
    roles: ['SECRETAIRE', 'CHEF_SERVICE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/notes-internes', libelle: 'Notes internes', icone: 'edit',
    roles: ['SECRETAIRE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/contrats', libelle: 'Contrats', icone: 'briefcase',
    roles: ['CHEF_SERVICE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/prestations-services', libelle: 'Prestations de services', icone: 'briefcase',
    roles: ['CHEF_SERVICE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/stocks', libelle: 'Gestion de stocks', icone: 'archive',
    roles: ['CHEF_SERVICE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    lien: '/rapports-administratifs', libelle: 'Rapports administratifs', icone: 'presentation',
    roles: ['COMPTABLE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
  {
    // Sans restriction de rôle : n'importe quel salarié demande une sortie
    // de caisse, c'est le destinataire du bon qui autorise. Restreindre ici
    // reviendrait à cacher le formulaire à ceux qui en ont besoin.
    lien: '/bon-sortie-caisse', libelle: 'Caisse et bons de sortie', icone: 'wallet',
  },
  {
    lien: '/deplacements', libelle: 'Gestion des déplacements', icone: 'car',
    roles: ['SECRETAIRE', 'COMPTABLE', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
];

/**
 * Modules « vie interne » : congés, événements, mémoire du groupe.
 *
 * Ouverts à tous les utilisateurs connectés — chacun pose ses congés,
 * consulte les événements et dépose des photos. Ils sont listés à part des
 * « Moyens Généraux », qui relèvent d'un circuit administratif, pour que la
 * navigation distingue les deux familles.
 */
export const MODULES_VIE_INTERNE: ModuleMetier[] = [
  { lien: '/conges', libelle: 'Congés et permissions', icone: 'sun' },
  // Recevoir une note concerne tout le monde ; la rédiger reste réservé
  // aux secrétaires et à la direction (voir /notes-internes).
  { lien: '/notes-recues', libelle: 'Notes de service', icone: 'doc' },
  { lien: '/evenements', libelle: 'Événements', icone: 'gift' },
  { lien: '/galerie', libelle: 'Mémoire / Galerie', icone: 'image' },
  {
    // Visible seulement pour ceux qui instruisent : un salarié n'y arrive
    // que par la notification de son propre dossier.
    lien: '/discipline', libelle: 'Discipline', icone: 'shield',
    roles: ['RH', 'DIRECTEUR', 'ADMINISTRATEUR'],
  },
];

// Modules déjà implémentés (moteur générique de documents administratifs) :
// chemin -> type de document côté API. Source unique utilisée par les
// routes (app.routes.ts) et par la navigation au clic sur une notification
// (shell.component.ts), pour ne jamais désynchroniser les deux.
export const CHEMIN_PAR_TYPE_DOCUMENT: Record<string, string> = {
  FICHE_BESOIN: '/fiche-besoin',
  DEMANDE_ACHAT: '/demandes-achat',
  FICHE_TRANSPORT: '/deplacements',
  BON_SORTIE_CAISSE: '/bon-sortie-caisse',
  BON_COMMANDE: '/bons-commande',
  NOTE_INTERNE: '/notes-internes',
  FACTURE: '/factures',
};
