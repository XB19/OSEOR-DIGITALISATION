import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { DialogueService } from '../../core/dialogue.service';
import { ToastService } from '../../core/toast.service';
import { IconComponent } from '../../shared/icon.component';
import { Visite } from '../../core/models';

@Component({
  selector: 'app-visiteurs',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="entete anim-entree">
    <div>
      <h1>Visiteurs</h1>
      <p class="sous-titre">Registre d'accueil — enregistrement, validation par le secrétariat et suivi des départs</p>
    </div>
  </div>

  <div class="carte anim-entree">
    <h3>Enregistrer une arrivée</h3>
    <p class="aide">La pièce d'identité du visiteur est conservée à l'accueil jusqu'à son départ. La demande part au secrétariat pour validation.</p>
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
          <input type="text" inputmode="numeric" pattern="[0-9]*"
                 [ngModel]="form.numero_piece" (ngModelChange)="fixerNumeroPiece($event)"
                 name="numero_piece" placeholder="Chiffres uniquement" required autocomplete="off" />
        </div>
      </div>
      <div class="champ">
        <label>Motif de la visite</label>
        <input type="text" [(ngModel)]="form.motif" name="motif" placeholder="Ex. rendez-vous, livraison, entretien…" required autocomplete="off" />
      </div>
      <button type="submit" class="btn cta" [disabled]="enregistrementEnCours() || !formValide()">
        @if (enregistrementEnCours()) { <span class="spinner petit"></span> Enregistrement… }
        @else { <app-icon name="plus"/> Enregistrer l'arrivée }
      </button>
    </form>
  </div>

  <div class="carte anim-entree espace">
    <h3>Demandes en attente de validation ({{ enAttente().length }})</h3>
    @if (chargement()) {
      <p class="vide">Chargement…</p>
    } @else if (enAttente().length === 0) {
      <p class="vide">Aucune demande en attente.</p>
    } @else {
      <table class="tbl">
        <thead>
          <tr><th>Visiteur</th><th>Motif</th><th>N° pièce</th><th>Enregistré par</th><th>Heure</th>
            @if (peutTraiter()) { <th></th> }</tr>
        </thead>
        <tbody class="stagger">
          @for (v of enAttente(); track v.id) {
            <tr>
              <td>{{ v.prenom }} {{ v.nom }}</td>
              <td>{{ v.motif }}</td>
              <td>{{ v.numero_piece }}</td>
              <td>{{ v.enregistre_par_nom }}</td>
              <td>{{ v.heure_arrivee | date:'HH:mm' }}</td>
              @if (peutTraiter()) {
                <td>
                  <div class="actions">
                    <button class="btn vert petit" (click)="valider(v)" [disabled]="actionEnCours() === v.id">
                      <app-icon name="check" [size]="14"/> Valider
                    </button>
                    <button class="btn rouge petit" (click)="refuser(v)" [disabled]="actionEnCours() === v.id">
                      <app-icon name="close" [size]="14"/> Refuser
                    </button>
                  </div>
                </td>
              }
            </tr>
          }
        </tbody>
      </table>
    }
  </div>

  <div class="carte anim-entree espace">
    <h3>Présents ({{ presents().length }})</h3>
    @if (!chargement() && presents().length === 0) {
      <p class="vide">Aucun visiteur sur place actuellement.</p>
    } @else if (!chargement()) {
      <table class="tbl">
        <thead>
          <tr><th>Visiteur</th><th>Motif</th><th>N° pièce</th><th>Validé par</th><th>Heure d'arrivée</th><th></th></tr>
        </thead>
        <tbody class="stagger">
          @for (v of presents(); track v.id) {
            <tr>
              <td>{{ v.prenom }} {{ v.nom }}</td>
              <td>{{ v.motif }}</td>
              <td>{{ v.numero_piece }}</td>
              <td>{{ v.traite_par_nom }}</td>
              <td>{{ v.heure_arrivee | date:'HH:mm' }}</td>
              <td>
                <button class="btn secondaire petit" (click)="depart(v)" [disabled]="actionEnCours() === v.id">
                  @if (actionEnCours() === v.id) { <span class="spinner petit"></span> }
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
    @if (!chargement() && historique().length === 0) {
      <p class="vide">Aucune visite terminée ou refusée pour le moment.</p>
    } @else if (!chargement()) {
      <table class="tbl">
        <thead>
          <tr><th>Visiteur</th><th>Motif</th><th>Arrivée</th><th>Départ</th><th>Statut</th></tr>
        </thead>
        <tbody class="stagger">
          @for (v of historique(); track v.id) {
            <tr>
              <td>{{ v.prenom }} {{ v.nom }}</td>
              <td>{{ v.motif }}</td>
              <td>{{ v.heure_arrivee | date:'dd/MM/yyyy HH:mm' }}</td>
              <td>{{ v.heure_depart ? (v.heure_depart | date:'dd/MM/yyyy HH:mm') : '—' }}</td>
              <td>
                @if (v.statut === 'REFUSEE') {
                  <span class="badge refusee">Refusé</span>
                  @if (v.motif_refus) { <div class="motif-refus">{{ v.motif_refus }}</div> }
                } @else {
                  <span class="badge validee">Parti</span>
                }
              </td>
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
    .actions { display: flex; gap: .4rem; flex-wrap: wrap; }
    .motif-refus { font-size: .76rem; color: var(--txt-3); margin-top: .2rem; }
  `],
})
export class VisiteursComponent implements OnInit {
  visites = signal<Visite[]>([]);
  chargement = signal(false);
  enregistrementEnCours = signal(false);
  actionEnCours = signal<number | null>(null);

  form = { nom: '', prenom: '', numero_piece: '', motif: '' };

  constructor(
    private api: ApiService, public auth: AuthService,
    private dialogue: DialogueService, private toasts: ToastService,
  ) {}

  ngOnInit(): void {
    this.charger();
  }

  peutTraiter(): boolean {
    return this.auth.aRole('SECRETAIRE', 'ADMINISTRATEUR', 'DIRECTEUR');
  }

  formValide(): boolean {
    return !!(this.form.nom.trim() && this.form.prenom.trim() && this.form.numero_piece.trim() && this.form.motif.trim());
  }

  /** Ne garde que les chiffres saisis (numéro de pièce d'identité). */
  fixerNumeroPiece(valeur: string): void {
    this.form.numero_piece = valeur.replace(/\D/g, '');
  }

  enAttente() {
    return this.visites().filter((v) => v.statut === 'EN_ATTENTE');
  }

  presents() {
    return this.visites().filter((v) => v.statut === 'VALIDEE');
  }

  historique() {
    return this.visites().filter((v) => v.statut === 'REFUSEE' || v.statut === 'TERMINEE');
  }

  private erreurToast(titre: string, e: any): void {
    this.toasts.afficher({ titre, message: e?.error?.detail || e?.error?.[0] || 'Erreur inconnue.', type: 'ERROR' });
  }

  charger(): void {
    this.chargement.set(true);
    this.api.visites({ page_size: 100 }).subscribe({
      next: (p) => { this.chargement.set(false); this.visites.set(p.results); },
      error: (e) => { this.chargement.set(false); this.erreurToast('Chargement impossible', e); },
    });
  }

  enregistrerArrivee(): void {
    if (!this.formValide()) return;
    this.enregistrementEnCours.set(true);
    this.api.creerVisite({
      nom: this.form.nom.trim(),
      prenom: this.form.prenom.trim(),
      numero_piece: this.form.numero_piece.trim(),
      motif: this.form.motif.trim(),
    }).subscribe({
      next: (v) => {
        this.enregistrementEnCours.set(false);
        this.visites.update((liste) => [v, ...liste]);
        this.form = { nom: '', prenom: '', numero_piece: '', motif: '' };
        this.toasts.succes('Demande envoyée au secrétariat pour validation.');
      },
      error: (e) => {
        this.enregistrementEnCours.set(false);
        this.erreurToast("Impossible d'enregistrer cette arrivée", e);
      },
    });
  }

  valider(v: Visite): void {
    this.actionEnCours.set(v.id);
    this.api.validerVisite(v.id).subscribe({
      next: (maj) => {
        this.actionEnCours.set(null);
        this.visites.update((liste) => liste.map((x) => (x.id === maj.id ? maj : x)));
      },
      error: (e) => { this.actionEnCours.set(null); this.erreurToast('Validation impossible', e); },
    });
  }

  async refuser(v: Visite): Promise<void> {
    const motif = await this.dialogue.demanderMotif({
      titre: 'Refuser la visite',
      message: `${v.prenom} ${v.nom} — ${v.motif}`,
      placeholder: 'Motif du refus',
      libelleConfirmer: 'Refuser',
      dangereux: true,
      obligatoire: true,
    });
    if (motif === null) return;
    this.actionEnCours.set(v.id);
    this.api.refuserVisite(v.id, motif).subscribe({
      next: (maj) => {
        this.actionEnCours.set(null);
        this.visites.update((liste) => liste.map((x) => (x.id === maj.id ? maj : x)));
      },
      error: (e) => { this.actionEnCours.set(null); this.erreurToast('Refus impossible', e); },
    });
  }

  depart(v: Visite): void {
    this.actionEnCours.set(v.id);
    this.api.marquerDepartVisite(v.id).subscribe({
      next: (maj) => {
        this.actionEnCours.set(null);
        this.visites.update((liste) => liste.map((x) => (x.id === maj.id ? maj : x)));
      },
      error: (e) => { this.actionEnCours.set(null); this.erreurToast("Impossible d'enregistrer ce départ", e); },
    });
  }
}
