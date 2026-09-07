import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { IconComponent } from '../../shared/icon.component';
import { Visite } from '../../core/models';

@Component({
  selector: 'app-visiteurs',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="entete anim-entree">
    <div>
      <h1>Visiteurs</h1>
      <p class="sous-titre">Registre d'accueil — enregistrement des arrivées et des départs</p>
    </div>
  </div>

  @if (erreur()) {
    <div class="alerte err anim-entree"><app-icon name="close" [size]="16"/> {{ erreur() }}</div>
  }

  <div class="carte anim-entree">
    <h3>Enregistrer une arrivée</h3>
    <p class="aide">La pièce d'identité du visiteur est conservée à l'accueil jusqu'à son départ.</p>
    <form (ngSubmit)="enregistrerArrivee()">
      <div class="ligne">
        <div class="champ">
          <label>Nom</label>
          <input type="text" [(ngModel)]="form.nom" name="nom" required autocomplete="off" />
        </div>
        <div class="champ">
          <label>Prénom</label>
          <input type="text" [(ngModel)]="form.prenom" name="prenom" required autocomplete="off" />
        </div>
        <div class="champ">
          <label>Numéro de pièce d'identité</label>
          <input type="text" [(ngModel)]="form.numero_piece" name="numero_piece" required autocomplete="off" />
        </div>
      </div>
      <button type="submit" class="btn cta" [disabled]="enregistrementEnCours() || !formValide()">
        @if (enregistrementEnCours()) { <span class="spinner petit"></span> Enregistrement… }
        @else { <app-icon name="plus"/> Enregistrer l'arrivée }
      </button>
    </form>
  </div>

  <div class="carte anim-entree espace">
    <h3>Présents ({{ presents().length }})</h3>
    @if (chargement()) {
      <p class="vide">Chargement…</p>
    } @else if (presents().length === 0) {
      <p class="vide">Aucun visiteur sur place actuellement.</p>
    } @else {
      <table class="tbl">
        <thead>
          <tr><th>Visiteur</th><th>N° pièce</th><th>Heure d'arrivée</th><th>Enregistré par</th><th></th></tr>
        </thead>
        <tbody class="stagger">
          @for (v of presents(); track v.id) {
            <tr>
              <td>{{ v.prenom }} {{ v.nom }}</td>
              <td>{{ v.numero_piece }}</td>
              <td>{{ v.heure_arrivee | date:'HH:mm' }}</td>
              <td>{{ v.enregistre_par_nom }}</td>
              <td>
                <button class="btn secondaire petit" (click)="depart(v)" [disabled]="departEnCours() === v.id">
                  @if (departEnCours() === v.id) { <span class="spinner petit"></span> }
                  @else { <app-icon name="logout" [size]="15"/> Marquer le départ }
                </button>
              </td>
            </tr>
          }
        </tbody>
      </table>
    }
  </div>

  <div class="carte anim-entree espace">
    <h3>Historique récent</h3>
    @if (!chargement() && partis().length === 0) {
      <p class="vide">Aucun départ enregistré pour le moment.</p>
    } @else if (!chargement()) {
      <table class="tbl">
        <thead>
          <tr><th>Visiteur</th><th>N° pièce</th><th>Arrivée</th><th>Départ</th><th></th></tr>
        </thead>
        <tbody class="stagger">
          @for (v of partis(); track v.id) {
            <tr>
              <td>{{ v.prenom }} {{ v.nom }}</td>
              <td>{{ v.numero_piece }}</td>
              <td>{{ v.heure_arrivee | date:'dd/MM/yyyy HH:mm' }}</td>
              <td>{{ v.heure_depart | date:'dd/MM/yyyy HH:mm' }}</td>
              <td><span class="badge validee">Parti</span></td>
            </tr>
          }
        </tbody>
      </table>
    }
  </div>
  `,
  styles: [`
    .entete { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
    .sous-titre { color: var(--txt-2); font-size: .82rem; margin: .2rem 0 0; }
    .aide { color: var(--txt-3); font-size: .82rem; margin: -.4rem 0 1rem; }
    .espace { margin-top: 1.2rem; }
  `],
})
export class VisiteursComponent implements OnInit {
  visites = signal<Visite[]>([]);
  chargement = signal(false);
  enregistrementEnCours = signal(false);
  departEnCours = signal<number | null>(null);
  erreur = signal('');

  form = { nom: '', prenom: '', numero_piece: '' };

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.charger();
  }

  formValide(): boolean {
    return !!(this.form.nom.trim() && this.form.prenom.trim() && this.form.numero_piece.trim());
  }

  presents() {
    return this.visites().filter((v) => v.presente);
  }

  partis() {
    return this.visites().filter((v) => !v.presente);
  }

  charger(): void {
    this.erreur.set('');
    this.chargement.set(true);
    this.api.visites({ page_size: 100 }).subscribe({
      next: (p) => { this.chargement.set(false); this.visites.set(p.results); },
      error: () => { this.chargement.set(false); this.erreur.set('Impossible de charger le registre des visiteurs.'); },
    });
  }

  enregistrerArrivee(): void {
    if (!this.formValide()) return;
    this.erreur.set('');
    this.enregistrementEnCours.set(true);
    this.api.creerVisite({
      nom: this.form.nom.trim(),
      prenom: this.form.prenom.trim(),
      numero_piece: this.form.numero_piece.trim(),
    }).subscribe({
      next: (v) => {
        this.enregistrementEnCours.set(false);
        this.visites.update((liste) => [v, ...liste]);
        this.form = { nom: '', prenom: '', numero_piece: '' };
      },
      error: () => {
        this.enregistrementEnCours.set(false);
        this.erreur.set("Impossible d'enregistrer cette arrivée.");
      },
    });
  }

  depart(v: Visite): void {
    this.departEnCours.set(v.id);
    this.api.marquerDepartVisite(v.id).subscribe({
      next: (maj) => {
        this.departEnCours.set(null);
        this.visites.update((liste) => liste.map((x) => (x.id === maj.id ? maj : x)));
      },
      error: () => {
        this.departEnCours.set(null);
        this.erreur.set("Impossible d'enregistrer ce départ.");
      },
    });
  }
}
