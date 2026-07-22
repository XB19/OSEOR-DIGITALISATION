import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { Salle } from '../../core/models';
import { IconComponent } from '../../shared/icon.component';

interface JourOption { val: number; lbl: string; }

@Component({
  selector: 'app-recurrence',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <h1 class="anim-entree"><app-icon name="repeat" [size]="24"/> Réservation récurrente</h1>
  <p class="sous anim-entree">Planifiez une réunion qui se répète (ex. chaque lundi 9h–10h). Le système
    crée chaque occurrence et signale automatiquement les créneaux en conflit.</p>

  <div class="carte form anim-entree">
    <div class="ligne">
      <div class="champ"><label>Salle</label>
        <select [(ngModel)]="form.salle">
          <option [ngValue]="null">— choisir —</option>
          @for (s of salles(); track s.id) {
            <option [ngValue]="s.id">{{ s.nom }} — {{ s.filiale_nom }} ({{ s.capacite }} pl.)</option>
          }
        </select>
      </div>
      <div class="champ"><label>Nom du réservant</label><input [(ngModel)]="form.nom_reservant" /></div>
      <div class="champ"><label>Téléphone</label><input [(ngModel)]="form.telephone" /></div>
    </div>

    <div class="champ"><label>Motif / objet de la réunion</label>
      <input [(ngModel)]="form.motif" placeholder="ex. Réunion d'équipe hebdomadaire" /></div>

    <div class="ligne">
      <div class="champ"><label>Fréquence</label>
        <select [(ngModel)]="form.frequence">
          <option value="QUOTIDIENNE">Tous les jours ouvrés</option>
          <option value="HEBDOMADAIRE">Chaque semaine</option>
          <option value="BIHEBDOMADAIRE">Une semaine sur deux</option>
          <option value="MENSUELLE">Chaque mois</option>
        </select>
      </div>
      <div class="champ"><label>Début (heure)</label><input type="time" [(ngModel)]="form.heure_debut" /></div>
      <div class="champ"><label>Fin (heure)</label><input type="time" [(ngModel)]="form.heure_fin" /></div>
    </div>

    @if (form.frequence === 'HEBDOMADAIRE' || form.frequence === 'BIHEBDOMADAIRE') {
      <div class="champ"><label>Jours de la semaine</label>
        <div class="jours">
          @for (j of jours; track j.val) {
            <button type="button" class="jour" [class.on]="aJour(j.val)" (click)="basculerJour(j.val)">{{ j.lbl }}</button>
          }
        </div>
      </div>
    }

    <div class="ligne">
      <div class="champ"><label>Du</label><input type="date" [(ngModel)]="form.date_debut" /></div>
      <div class="champ"><label>Au</label><input type="date" [(ngModel)]="form.date_fin" /></div>
    </div>

    <div class="champ"><label>Précisions</label><textarea rows="2" [(ngModel)]="form.precisions"></textarea></div>

    @if (erreur()) { <div class="alerte err"><app-icon name="close" [size]="16"/>{{ erreur() }}</div> }
    @if (resultat(); as r) {
      <div class="alerte ok"><app-icon name="checkCircle" [size]="16"/>
        Série créée : <strong>{{ r.recurrence?.occurrences_creees }}</strong> occurrence(s) planifiée(s).
        @if (r.recurrence?.occurrences_en_conflit?.length) {
          {{ r.recurrence.occurrences_en_conflit.length }} créneau(x) ignoré(s) pour cause de conflit.
        }
      </div>
    }

    <div style="margin-top:1rem">
      <button class="btn cta" [disabled]="envoi()" (click)="creer()">
        @if (envoi()) { <span class="spinner"></span> Création… }
        @else { <app-icon name="repeat" [size]="17"/> Créer la série }
      </button>
    </div>
  </div>
  `,
  styles: [`
    h1 { display: flex; align-items: center; gap: .6rem; }
    h1 app-icon { color: var(--accent); }
    .sous { color: var(--txt-2); margin-top: -.3rem; max-width: 680px; }
    .form { max-width: 760px; margin-top: 1rem; }
    .jours { display: flex; gap: .4rem; flex-wrap: wrap; }
    .jour { padding: .5rem .8rem; border-radius: 8px; border: 1px solid var(--bord-fort);
      background: #fff; cursor: pointer; font-weight: 600; font-size: .85rem; color: var(--txt-2);
      transition: all var(--t); }
    .jour:hover { border-color: var(--bleu); }
    .jour.on { background: var(--navy); color: #fff; border-color: var(--navy); }
  `],
})
export class RecurrenceComponent implements OnInit {
  salles = signal<Salle[]>([]);
  envoi = signal(false);
  erreur = signal('');
  resultat = signal<any | null>(null);

  jours: JourOption[] = [
    { val: 0, lbl: 'Lun' }, { val: 1, lbl: 'Mar' }, { val: 2, lbl: 'Mer' },
    { val: 3, lbl: 'Jeu' }, { val: 4, lbl: 'Ven' }, { val: 5, lbl: 'Sam' }, { val: 6, lbl: 'Dim' },
  ];

  form: any = {
    salle: null, nom_reservant: '', telephone: '', motif: '', frequence: 'HEBDOMADAIRE',
    jours_semaine: [], heure_debut: '', heure_fin: '', date_debut: '', date_fin: '', precisions: '',
  };

  constructor(private api: ApiService, private auth: AuthService) {}

  ngOnInit(): void {
    this.api.salles().subscribe((p) => this.salles.set(p.results));
    this.form.nom_reservant = this.auth.utilisateur()?.nom_complet ?? '';
    this.form.telephone = this.auth.utilisateur()?.telephone ?? '';
  }

  aJour(v: number): boolean { return this.form.jours_semaine.includes(v); }
  basculerJour(v: number): void {
    this.form.jours_semaine = this.aJour(v)
      ? this.form.jours_semaine.filter((x: number) => x !== v)
      : [...this.form.jours_semaine, v];
  }

  creer(): void {
    this.erreur.set(''); this.resultat.set(null);
    if (!this.form.salle || !this.form.heure_debut || !this.form.heure_fin
        || !this.form.date_debut || !this.form.date_fin) {
      this.erreur.set('Salle, horaires et période sont requis.');
      return;
    }
    if (this.form.date_debut >= this.form.date_fin) {
      this.erreur.set("La période doit couvrir plus d'un jour (date de fin après la date de début). "
        + 'Pour une seule date, utilisez « Réserver une salle ».');
      return;
    }
    this.envoi.set(true);
    this.api.creerSerie(this.form).subscribe({
      next: (r) => {
        this.envoi.set(false);
        this.resultat.set(r);
        this.reinitialiser();
      },
      error: (e) => {
        this.envoi.set(false);
        const d = e?.error;
        this.erreur.set(typeof d === 'string' ? d
          : (d?.detail || Object.values(d || {}).flat().join(' ') || 'Erreur lors de la création.'));
      },
    });
  }

  private reinitialiser(): void {
    this.form = {
      salle: null,
      nom_reservant: this.auth.utilisateur()?.nom_complet ?? '',
      telephone: this.auth.utilisateur()?.telephone ?? '',
      motif: '',
      frequence: 'HEBDOMADAIRE',
      jours_semaine: [],
      heure_debut: '',
      heure_fin: '',
      date_debut: '',
      date_fin: '',
      precisions: '',
    };
  }
}
