import { Reservation } from '../core/models';

/**
 * Groupe de réservations : soit une réservation simple, soit toutes les
 * occurrences d'une série récurrente regroupées sur une seule ligne.
 */
export interface GroupeReservations {
  estSerie: boolean;
  premiere: Reservation;
  occurrences: Reservation[];
}

/** Regroupe les occurrences d'une même série en un seul élément. */
export function grouperParSerie(liste: Reservation[]): GroupeReservations[] {
  const groupes: GroupeReservations[] = [];
  const parSerie = new Map<number, GroupeReservations>();
  for (const r of liste) {
    if (r.serie) {
      let g = parSerie.get(r.serie);
      if (!g) {
        g = { estSerie: true, premiere: r, occurrences: [] };
        parSerie.set(r.serie, g);
        groupes.push(g);
      }
      g.occurrences.push(r);
    } else {
      groupes.push({ estSerie: false, premiere: r, occurrences: [r] });
    }
  }
  return groupes;
}

/** « sur 1 semaine », « sur 3 semaines », « sur 1 mois », « sur 2 mois »… */
export function libelleDuree(debut?: string | null, fin?: string | null): string {
  if (!debut || !fin) return '';
  const jours = Math.round(
    (new Date(fin).getTime() - new Date(debut).getTime()) / 86_400_000,
  ) + 1;
  if (jours >= 55) return `sur ${Math.round(jours / 30)} mois`;
  if (jours >= 25) return 'sur 1 mois';
  if (jours >= 13) return `sur ${Math.round(jours / 7)} semaines`;
  if (jours >= 6) return 'sur 1 semaine';
  return `sur ${jours} jour${jours > 1 ? 's' : ''}`;
}

/** « Chaque semaine · du 08/07/2026 au 29/07/2026 · sur 1 mois ». */
export function libelleSerie(r: Reservation): string {
  const fr = (d?: string | null) =>
    d ? new Date(d + 'T12:00:00').toLocaleDateString('fr-FR') : '';
  const parties = [
    r.serie_frequence || 'Récurrente',
    r.serie_date_debut && r.serie_date_fin
      ? `du ${fr(r.serie_date_debut)} au ${fr(r.serie_date_fin)}`
      : '',
    libelleDuree(r.serie_date_debut, r.serie_date_fin),
  ];
  return parties.filter(Boolean).join(' · ');
}

/** Résumé des statuts d'un groupe : « 2 × Validée · 1 × En attente ». */
export function resumeStatuts(occurrences: Reservation[]): string {
  const compte = new Map<string, number>();
  for (const o of occurrences) {
    const lbl = o.statut_libelle || o.statut;
    compte.set(lbl, (compte.get(lbl) || 0) + 1);
  }
  return [...compte.entries()].map(([lbl, n]) => `${n} × ${lbl}`).join(' · ');
}
