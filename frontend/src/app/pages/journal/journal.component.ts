import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/api.service';

const LIBELLES: Record<string, string> = {
  RESERVATION_CREEE: 'Réservation créée',
  RESERVATION_VALIDEE: 'Réservation validée',
  RESERVATION_REFUSEE: 'Réservation refusée',
  RESERVATION_ANNULEE: 'Réservation annulée',
  RESERVATION_DEPLACEE: 'Réservation déplacée',
  AUDIENCE_VALIDEE_DG: 'Audience validée (DG)',
  AUDIENCE_DELEGUEE: 'Audience déléguée',
  AUDIENCE_CONFIRMEE: 'Audience confirmée',
  SALLE_CREEE: 'Salle créée',
  SALLE_SUPPRIMEE: 'Salle supprimée',
  UTILISATEUR_CREE: 'Utilisateur créé',
  UTILISATEUR_MODIFIE: 'Utilisateur modifié',
};

@Component({
  selector: 'app-journal',
  imports: [CommonModule],
  template: `
  <h1 class="anim-entree">Journal d'audit</h1>
  <p class="sous anim-entree">Historique horodaté des actions sensibles (EF-20).</p>

  <div class="carte anim-entree">
    @if (entrees().length) {
      <table class="tbl">
        <tr><th>Date</th><th>Action</th><th>Acteur</th><th>Cible</th></tr>
        @for (e of entrees(); track e.id) {
          <tr>
            <td>{{ e.date_creation | date:'dd/MM/yyyy HH:mm' }}</td>
            <td><span class="badge" [class]="classe(e.action)">{{ libelle(e.action) }}</span></td>
            <td>{{ e.acteur_nom || 'Système' }}</td>
            <td>{{ e.cible }}</td>
          </tr>
        }
      </table>
    } @else { <div class="vide">Aucune action enregistrée.</div> }
  </div>
  `,
  styles: [`.sous { color: var(--txt-2); margin-top: -.3rem; }`],
})
export class JournalComponent implements OnInit {
  entrees = signal<any[]>([]);
  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.journal().subscribe((p) => this.entrees.set(p.results || []));
  }

  libelle(a: string): string { return LIBELLES[a] || a; }
  classe(a: string): string {
    if (a.includes('VALID') || a.includes('CONFIRM') || a.includes('CREE')) return 'validee';
    if (a.includes('REFUS') || a.includes('ANNUL') || a.includes('SUPPRIM')) return 'annulee';
    if (a.includes('DEPLAC') || a.includes('MODIF') || a.includes('DELEG')) return 'attente';
    return 'info';
  }
}
