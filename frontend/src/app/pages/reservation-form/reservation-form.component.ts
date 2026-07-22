import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Salle, Participant } from '../../core/models';
import { SalleVisuelleComponent } from '../../shared/salle-visuelle.component';
import { IconComponent } from '../../shared/icon.component';

@Component({
  selector: 'app-reservation-form',
  imports: [CommonModule, FormsModule, SalleVisuelleComponent, IconComponent],
  template: `
  <h1 class="anim-entree">{{ editId ? 'Modifier la réservation' : 'Nouvelle demande de réservation' }}</h1>

  <div class="deux anim-entree">
    <div class="carte">
      <h3>Détails de la réunion</h3>

      <div class="champ">
        <label>Salle</label>
        <select [(ngModel)]="form.salle" (ngModelChange)="onChangeSalle()">
          <option [ngValue]="null">— choisir —</option>
          @for (s of salles(); track s.id) {
            <option [ngValue]="s.id">{{ s.nom }} — {{ s.filiale_nom }} ({{ s.capacite }} pl.)</option>
          }
        </select>
      </div>

      <div class="ligne">
        <div class="champ"><label>Date</label>
          <input type="date" [(ngModel)]="form.date_reunion" (ngModelChange)="verifier()" /></div>
        <div class="champ"><label>Début</label>
          <input type="time" [(ngModel)]="form.heure_debut" (ngModelChange)="verifier()" /></div>
        <div class="champ"><label>Fin</label>
          <input type="time" [(ngModel)]="form.heure_fin" (ngModelChange)="verifier()" /></div>
      </div>

      @if (estValidee() && !modifiePourAutrui()) {
        <div class="alerte warn">
          <app-icon name="info" [size]="16"/>
          Cette réservation est <strong>validée</strong>. Toute modification la repassera
          <strong>en attente</strong> pour une nouvelle validation par le secrétariat.
        </div>
      }

      @if (modifiePourAutrui()) {
        <div class="alerte warn">
          <app-icon name="info" [size]="16"/>
          Vous modifiez la réservation de <strong>{{ demandeurNom }}</strong>.
          Il/elle sera notifié(e) du changement avec le motif ci-dessous.
        </div>
        <div class="champ"><label>Motif de la modification (transmis au demandeur)</label>
          <input [(ngModel)]="form.motif_modification"
                 placeholder="ex. le DG a besoin de la salle à 12h" /></div>
      }

      @if (dispoMessage()) {
        <div class="alerte" [class.err]="!disponible()" [class.ok]="disponible()">
          <app-icon [name]="disponible() ? 'checkCircle' : 'close'" [size]="16"/>
          {{ dispoMessage() }}
        </div>
      }

      <div class="champ"><label>Motif / objet de la réunion</label>
        <input [(ngModel)]="form.motif" placeholder="ex. Réunion d'équipe, entretien…" /></div>

      <div class="ligne">
        <div class="champ"><label>Nom du réservant</label>
          <input [(ngModel)]="form.nom_reservant" /></div>
        <div class="champ"><label>Téléphone</label>
          <input [(ngModel)]="form.telephone" placeholder="ex. 0700000000" /></div>
      </div>

      <div class="champ"><label>Précisions (café, boissons, matériel…)</label>
        <textarea rows="3" [(ngModel)]="form.precisions"></textarea></div>

      <h3 style="margin-top:1.2rem">Liste de présence</h3>
      <div class="annuaire">
        <app-icon name="search" [size]="16"/>
        <input placeholder="Convier un collègue (annuaire) — il sera notifié…"
               [(ngModel)]="rechercheCollegue" (ngModelChange)="chercherCollegue()" />
        @if (resultatsCollegues().length) {
          <div class="resultats">
            @for (u of resultatsCollegues(); track u.id) {
              <div class="res" (click)="ajouterCollegue(u)">
                {{ u.nom_complet }} <small>{{ u.email }}</small>
              </div>
            }
          </div>
        }
      </div>
      @for (p of participants(); track $index) {
        <div class="part" [class.interne]="p.utilisateur">
          <input placeholder="Nom" [(ngModel)]="p.nom" />
          <input placeholder="Prénom" [(ngModel)]="p.prenom" />
          <input placeholder="Email" [(ngModel)]="p.email" />
          <input placeholder="Téléphone" [(ngModel)]="p.telephone" />
          <input placeholder="Société" [(ngModel)]="p.societe" />
          <select [(ngModel)]="p.type_participant">
            <option value="INTERNE">Interne</option>
            <option value="EXTERNE">Externe</option>
          </select>
          <button class="btn rouge petit" (click)="retirer($index)" aria-label="Retirer"><app-icon name="close" [size]="14"/></button>
        </div>
      }
      <button class="btn secondaire petit" (click)="ajouter()"><app-icon name="plus" [size]="15"/> Ajouter un participant</button>

      @if (erreur()) { <div class="alerte err"><app-icon name="close" [size]="16"/>{{ erreur() }}</div> }

      <div style="margin-top:1.2rem">
        <button class="btn vert" [disabled]="!disponible() || envoi()" (click)="soumettre()">
          @if (envoi()) { <span class="spinner"></span> Envoi… }
          @else { <app-icon name="send" [size]="17"/> {{ editId ? 'Enregistrer les modifications' : 'Soumettre la demande' }} }
        </button>
      </div>
    </div>

    <div class="carte apercu">
      <h3>Aperçu de la salle</h3>
      @if (salleSelectionnee(); as s) {
        <app-salle-visuelle [salle]="s" />
        <div class="info"><strong>{{ s.nom }}</strong><br><small>{{ s.filiale_nom }}</small></div>
      } @else {
        <div class="vide">Sélectionnez une salle</div>
      }
    </div>
  </div>
  `,
  styles: [`
    .deux { display: grid; grid-template-columns: 1fr 280px; gap: 1rem; }
    @media (max-width: 850px) { .deux { grid-template-columns: 1fr; } }
    .part { display: grid; grid-template-columns: repeat(5, 1fr) auto auto; gap: .4rem;
      margin-bottom: .4rem; align-items: center; }
    .part input, .part select { min-width: 0; }
    .part.interne { background: #f0f7ff; border-radius: 8px; padding: .3rem; }
    .apercu { text-align: center; height: fit-content; }
    .info { margin-top: .8rem; }
    .annuaire { position: relative; display: flex; align-items: center; gap: .5rem;
      margin-bottom: .7rem; }
    .annuaire app-icon { color: var(--txt-3); }
    .annuaire input { flex: 1; }
    .resultats { position: absolute; top: 100%; left: 28px; right: 0; z-index: 20;
      background: #fff; border: 1px solid var(--bord); border-radius: 10px;
      box-shadow: var(--ombre-lg); max-height: 220px; overflow-y: auto; }
    .res { padding: .55rem .8rem; cursor: pointer; font-size: .88rem; }
    .res:hover { background: #f0f7ff; }
    .res small { color: var(--txt-3); }
  `],
})
export class ReservationFormComponent implements OnInit {
  salles = signal<Salle[]>([]);
  participants = signal<Participant[]>([]);
  disponible = signal(true);
  dispoMessage = signal('');
  envoi = signal(false);
  erreur = signal('');
  rechercheCollegue = '';
  resultatsCollegues = signal<any[]>([]);

  form: any = {
    salle: null, date_reunion: '', heure_debut: '', heure_fin: '',
    nom_reservant: '', telephone: '', motif: '', precisions: '',
  };

  salleSelectionnee = signal<Salle | null>(null);
  editId: number | null = null;
  estValidee = signal(false);
  demandeurId: number | null = null;
  demandeurNom = '';

  constructor(
    private api: ApiService, private auth: AuthService,
    private router: Router, private route: ActivatedRoute,
  ) {}

  ngOnInit(): void {
    this.api.salles().subscribe((p) => {
      this.salles.set(p.results);
      // En mode édition, recalcule l'aperçu une fois les salles chargées.
      if (this.editId) this.salleSelectionnee.set(p.results.find((s) => s.id === this.form.salle) ?? null);
    });
    const id = this.route.snapshot.queryParamMap.get('id');
    const copier = this.route.snapshot.queryParamMap.get('copier');
    if (id || copier) {
      if (id) this.editId = +id;
      this.api.reservation(+(id || copier)!).subscribe((r) => {
        this.form = {
          salle: r.salle, date_reunion: r.date_reunion,
          heure_debut: (r.heure_debut || '').slice(0, 5), heure_fin: (r.heure_fin || '').slice(0, 5),
          nom_reservant: r.nom_reservant, telephone: r.telephone || '',
          motif: r.motif || '', precisions: r.precisions || '',
        };
        this.estValidee.set(!!id && r.statut === 'VALIDEE');
        if (id) {
          this.demandeurId = r.demandeur ?? null;
          this.demandeurNom = r.demandeur_nom || r.nom_reservant;
          this.form.motif_modification = '';
        }
        // En mode copie (reprogrammation), on repart de zéro : nouveaux
        // participants sans id pour créer une nouvelle demande.
        this.participants.set((r.participants || []).map((p) => {
          const copie: any = { ...p };
          if (copier) { delete copie.id; }
          return copie;
        }));
        this.salleSelectionnee.set(this.salles().find((s) => s.id === r.salle) ?? null);
        this.verifier();
      });
    } else {
      this.form.nom_reservant = this.auth.utilisateur()?.nom_complet ?? '';
      this.form.telephone = this.auth.utilisateur()?.telephone ?? '';
    }
  }

  onChangeSalle(): void {
    this.salleSelectionnee.set(this.salles().find((s) => s.id === this.form.salle) ?? null);
    this.verifier();
  }

  /** Gestionnaire (secrétaire/admin) en train de modifier la réservation d'un autre. */
  modifiePourAutrui(): boolean {
    const u = this.auth.utilisateur();
    return !!this.editId && !!u
      && ['SECRETAIRE', 'ADMINISTRATEUR'].includes(u.role)
      && this.demandeurId !== null && this.demandeurId !== u.id;
  }

  ajouter(): void {
    this.participants.update((l) => [...l,
      { nom: '', prenom: '', email: '', telephone: '', societe: '', type_participant: 'INTERNE' }]);
  }
  retirer(i: number): void {
    this.participants.update((l) => l.filter((_, idx) => idx !== i));
  }

  chercherCollegue(): void {
    const q = this.rechercheCollegue.trim();
    if (q.length < 2) { this.resultatsCollegues.set([]); return; }
    this.api.rechercheUtilisateurs(q).subscribe((u) => this.resultatsCollegues.set(u));
  }

  ajouterCollegue(u: any): void {
    // Évite les doublons
    if (this.participants().some((p) => p.utilisateur === u.id)) {
      this.rechercheCollegue = ''; this.resultatsCollegues.set([]); return;
    }
    this.participants.update((l) => [...l, {
      nom: u.last_name || u.nom_complet, prenom: u.first_name || '',
      email: u.email, telephone: u.telephone || '',
      societe: u.filiale_nom || '', type_participant: 'INTERNE', utilisateur: u.id,
    }]);
    this.rechercheCollegue = '';
    this.resultatsCollegues.set([]);
  }

  verifier(): void {
    const f = this.form;
    if (!f.salle || !f.date_reunion || !f.heure_debut || !f.heure_fin) {
      this.dispoMessage.set(''); this.disponible.set(true); return;
    }
    if (f.heure_debut >= f.heure_fin) {
      this.disponible.set(false);
      this.dispoMessage.set("L'heure de fin doit être après l'heure de début.");
      return;
    }
    this.api.verifierDisponibilite({
      salle: f.salle, date_reunion: f.date_reunion,
      heure_debut: f.heure_debut, heure_fin: f.heure_fin,
      exclure: this.editId ?? undefined,
    }).subscribe((r) => {
      this.disponible.set(r.disponible);
      this.dispoMessage.set(r.disponible
        ? '✅ Créneau disponible.'
        : `⛔ Créneau déjà pris (${r.conflits.length} conflit(s)). Choisissez un autre horaire.`);
    });
  }

  soumettre(): void {
    this.erreur.set('');
    if (!this.disponible()) return;
    this.envoi.set(true);
    const payload = {
      ...this.form,
      participants: this.participants().filter((p) => p.nom),
    };
    const obs = this.editId
      ? this.api.majReservation(this.editId, payload)
      : this.api.creerReservation(payload);
    obs.subscribe({
      next: () => { this.envoi.set(false); this.router.navigate(['/mes-reservations']); },
      error: (e) => {
        this.envoi.set(false);
        const d = e?.error?.non_field_errors?.[0] || e?.error?.detail || 'Erreur lors de la soumission.';
        this.erreur.set(d);
      },
    });
  }
}
