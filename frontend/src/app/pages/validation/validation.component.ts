import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Reservation } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';
import {
  GroupeReservations, grouperParSerie, libelleSerie,
} from '../../shared/serie.util';

@Component({
  selector: 'app-validation',
  imports: [CommonModule, RouterLink, IconComponent],
  template: `
  <h1 class="anim-entree">Validation des demandes</h1>
  <p class="sous anim-entree">
    Demandes en attente sur les salles que vous gérez (RG-02)
    @if (filialeGeree(); as f) { — <strong>filiale {{ f }} uniquement</strong> }
    @else { — <strong>toutes les filiales</strong> }.
  </p>

  <div class="carte anim-entree">
    @if (enAttente().length) {
      <table class="tbl">
        <tr><th>Réservant</th><th>Motif</th><th>Salle</th><th>Date</th><th>Horaire</th><th>Précisions</th><th>Actions</th></tr>
        @for (g of enAttente(); track g.premiere.id) {
          <tr>
            <td>{{ g.premiere.nom_reservant }}<br><small>{{ g.premiere.demandeur_nom }}</small></td>
            <td>{{ g.premiere.motif || '—' }}</td>
            <td>{{ g.premiere.salle_nom }}</td>
            <td>
              @if (g.estSerie) {
                <span class="badge recurrente"><app-icon name="repeat" [size]="11"/> Récurrente</span><br>
                <small>{{ libelle(g.premiere) }}</small><br>
                <small><strong>{{ g.occurrences.length }} date{{ g.occurrences.length > 1 ? 's' : '' }} :</strong>
                  {{ datesDe(g) }}</small>
              } @else {
                {{ g.premiere.date_reunion }}
              }
            </td>
            <td>{{ g.premiere.heure_debut.slice(0,5) }}–{{ g.premiere.heure_fin.slice(0,5) }}</td>
            <td><small>{{ g.premiere.precisions || '—' }}</small></td>
            <td class="actions">
              <button class="btn vert petit" (click)="valider(g)">
                <app-icon name="check" [size]="14"/> Valider{{ g.estSerie ? ' la série' : '' }}</button>
              <button class="btn rouge petit" (click)="refuser(g)">
                <app-icon name="close" [size]="14"/> Refuser{{ g.estSerie ? ' la série' : '' }}</button>
            </td>
          </tr>
        }
      </table>
    } @else { <div class="vide">Aucune demande en attente. 🎉</div> }
  </div>

  <h2 style="margin-top:1.5rem">Réservations validées</h2>
  <div class="carte anim-entree">
    @if (validees().length) {
      <table class="tbl">
        <tr><th>Réservant</th><th>Salle</th><th>Date</th><th>Horaire</th><th>Arbitrage</th></tr>
        @for (g of validees(); track g.premiere.id) {
          @if (g.estSerie) {
            <tr class="ligne-serie" (click)="basculerSerie(g.premiere.serie!)">
              <td>{{ g.premiere.nom_reservant }}</td>
              <td>{{ g.premiere.salle_nom }}</td>
              <td>
                <span class="badge recurrente"><app-icon name="repeat" [size]="11"/> Récurrente</span><br>
                <small>{{ libelle(g.premiere) }}</small>
              </td>
              <td>{{ g.premiere.heure_debut.slice(0,5) }}–{{ g.premiere.heure_fin.slice(0,5) }}</td>
              <td>
                <button class="btn secondaire petit">
                  <app-icon [name]="serieOuverte() === g.premiere.serie ? 'chevronLeft' : 'chevronRight'" [size]="13"/>
                  {{ g.occurrences.length }} occurrence{{ g.occurrences.length > 1 ? 's' : '' }}
                </button>
              </td>
            </tr>
            @if (serieOuverte() === g.premiere.serie) {
              @for (r of g.occurrences; track r.id) {
                <tr class="occurrence">
                  <td><small>↳ occurrence</small></td>
                  <td>{{ r.salle_nom }}</td>
                  <td>{{ r.date_reunion }}</td>
                  <td>{{ r.heure_debut.slice(0,5) }}–{{ r.heure_fin.slice(0,5) }}</td>
                  <td class="actions">
                    <a class="btn secondaire petit" [routerLink]="['/reserver']" [queryParams]="{ id: r.id }"><app-icon name="edit" [size]="14"/> Modifier (avec motif)</a>
                    <button class="btn rouge petit" (click)="annulerRes(r)"><app-icon name="close" [size]="14"/> Annuler</button>
                  </td>
                </tr>
              }
            }
          } @else {
            <tr>
              <td>{{ g.premiere.nom_reservant }}</td>
              <td>{{ g.premiere.salle_nom }}</td>
              <td>{{ g.premiere.date_reunion }}</td>
              <td>{{ g.premiere.heure_debut.slice(0,5) }}–{{ g.premiere.heure_fin.slice(0,5) }}</td>
              <td class="actions">
                <a class="btn secondaire petit" [routerLink]="['/reserver']" [queryParams]="{ id: g.premiere.id }"><app-icon name="edit" [size]="14"/> Modifier (avec motif)</a>
                <button class="btn rouge petit" (click)="annulerRes(g.premiere)"><app-icon name="close" [size]="14"/> Annuler</button>
              </td>
            </tr>
          }
        }
      </table>
    } @else { <div class="vide">Aucune réservation validée.</div> }
  </div>
  `,
  styles: [`.sous{color:var(--gris-texte);margin-top:-.4rem;} .actions{display:flex;gap:.4rem;flex-wrap:wrap;} small{color:var(--gris-texte);}
    .badge.recurrente { background: #ede9fe; color: #6d28d9; display: inline-flex;
      align-items: center; gap: .25rem; }
    .ligne-serie { cursor: pointer; background: #faf9ff; }
    .ligne-serie:hover { background: #f3f0ff; }
    .occurrence { background: #fcfcfd; }
    .occurrence td:first-child { padding-left: 1.6rem; }`],
})
export class ValidationComponent implements OnInit {
  enAttente = signal<GroupeReservations[]>([]);
  validees = signal<GroupeReservations[]>([]);
  serieOuverte = signal<number | null>(null);

  constructor(private api: ApiService, private auth: AuthService) {}

  ngOnInit(): void { this.charger(); }

  private filtreFiliale(): Record<string, any> {
    const u = this.auth.utilisateur();
    // Secrétaire : restreint aux salles de sa filiale ; admin : tout.
    return u?.role === 'SECRETAIRE' && u.filiale ? { 'salle__filiale': u.filiale } : {};
  }

  /** Nom de la filiale gérée (null pour un admin = toutes). */
  filialeGeree(): string | null {
    const u = this.auth.utilisateur();
    return u?.role === 'SECRETAIRE' ? (u.filiale_nom ?? null) : null;
  }

  charger(): void {
    const base = this.filtreFiliale();
    this.api.reservations({ ...base, statut: 'EN_ATTENTE', page_size: 200 })
      .subscribe((p) => this.enAttente.set(grouperParSerie(p.results)));
    this.api.reservations({ ...base, statut: 'VALIDEE', page_size: 200 })
      .subscribe((p) => this.validees.set(grouperParSerie(p.results)));
  }

  basculerSerie(serieId: number): void {
    this.serieOuverte.set(this.serieOuverte() === serieId ? null : serieId);
  }

  libelle(r: Reservation): string { return libelleSerie(r); }

  datesDe(g: GroupeReservations): string {
    return g.occurrences.map((o) => o.date_reunion).join(', ');
  }

  valider(g: GroupeReservations): void {
    forkJoin(g.occurrences.map((o) => this.api.validerReservation(o.id))).subscribe({
      next: () => this.charger(),
      error: (e) => { alert(e?.error?.detail || 'Erreur.'); this.charger(); },
    });
  }

  refuser(g: GroupeReservations): void {
    const motif = prompt('Motif du refus ?') ?? '';
    forkJoin(g.occurrences.map((o) => this.api.refuserReservation(o.id, motif))).subscribe({
      next: () => this.charger(),
      error: (e) => { alert(e?.error?.detail || 'Erreur.'); this.charger(); },
    });
  }

  annulerRes(r: Reservation): void {
    const motif = prompt("Motif de l'annulation ? (transmis au demandeur, ex. « le DG a besoin de la salle »)");
    if (motif === null) return;
    this.api.annulerReservation(r.id, motif).subscribe({ next: () => this.charger(),
      error: (e) => alert(e?.error?.detail || 'Erreur.') });
  }
}
