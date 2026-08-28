import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/api.service';
import { AuthService } from '../../core/auth.service';
import { IconComponent } from '../../shared/icon.component';
import { Filiale, RapportAdministratif } from '../../core/models';

function premierJourDuMois(): string {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().slice(0, 10);
}

function aujourdHui(): string {
  return new Date().toISOString().slice(0, 10);
}

@Component({
  selector: 'app-rapports',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="entete anim-entree">
    <div>
      <h1>Rapports administratifs</h1>
      <p class="sous-titre">Consolidation comptable et administrative — documents, contrats, stocks</p>
    </div>
    <button class="btn cta" (click)="exporter()" [disabled]="exportEnCours() || chargement()">
      @if (exportEnCours()) { <span class="spinner petit"></span> Export… } @else { <app-icon name="doc"/> Exporter en PDF }
    </button>
  </div>

  <div class="carte filtres anim-entree">
    <div class="champ"><label>Du</label><input type="date" [(ngModel)]="dateDebut" (ngModelChange)="charger()" /></div>
    <div class="champ"><label>Au</label><input type="date" [(ngModel)]="dateFin" (ngModelChange)="charger()" /></div>
    @if (auth.aRole('ADMINISTRATEUR', 'DIRECTEUR')) {
      <div class="champ">
        <label>Filiale</label>
        <select [(ngModel)]="filialeId" (ngModelChange)="charger()">
          <option [ngValue]="null">Groupe (toutes filiales)</option>
          @for (f of filiales(); track f.id) { <option [ngValue]="f.id">{{ f.nom }}</option> }
        </select>
      </div>
    }
  </div>

  @if (erreur()) {
    <div class="alerte err anim-entree"><app-icon name="close" [size]="16"/> {{ erreur() }}</div>
  }

  @if (rapport(); as r) {
    <p class="portee anim-entree">{{ r.filiale }} — du {{ r.periode.date_debut | date:'dd/MM/yyyy' }} au {{ r.periode.date_fin | date:'dd/MM/yyyy' }}</p>

    <div class="grille stagger">
      <div class="kpi">
        <div class="ic ic-vert"><app-icon name="cart"/></div>
        <div><div class="v">{{ r.documents.montant_total_valide | number:'1.0-0' }}</div><div class="l">Montant validé (documents)</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-navy"><app-icon name="briefcase"/></div>
        <div><div class="v">{{ r.contrats.montant_engage | number:'1.0-0' }}</div><div class="l">Montant engagé (contrats actifs)</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-orange"><app-icon name="clock"/></div>
        <div><div class="v">{{ r.contrats.echeances_proches_30j }}</div><div class="l">Échéances de contrat &lt; 30j</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-bleu"><app-icon name="archive"/></div>
        <div><div class="v">{{ r.stocks.mouvements_total }}</div><div class="l">Mouvements de stock</div></div>
      </div>
      <div class="kpi">
        <div class="ic ic-orange"><app-icon name="close"/></div>
        <div><div class="v">{{ r.stocks.articles_en_alerte }}</div><div class="l">Articles en alerte de stock</div></div>
      </div>
    </div>

    <div class="carte anim-entree">
      <h3>Documents par type</h3>
      <table class="tbl">
        <thead>
          <tr><th>Type</th><th>Total</th><th>En cours</th><th>Validés</th><th>Refusés</th><th>Montant validé</th></tr>
        </thead>
        <tbody>
          @for (l of r.documents.par_type; track l.type_document) {
            <tr>
              <td>{{ l.type_document_libelle }}</td>
              <td>{{ l.total }}</td>
              <td>{{ l.en_cours }}</td>
              <td>{{ l.valides }}</td>
              <td>{{ l.refuses }}</td>
              <td>{{ l.montant_valide | number:'1.2-2' }}</td>
            </tr>
          }
        </tbody>
        <tfoot>
          <tr class="total"><td>Total</td><td>{{ r.documents.total_documents }}</td><td></td><td></td><td></td><td>{{ r.documents.montant_total_valide | number:'1.2-2' }}</td></tr>
        </tfoot>
      </table>
    </div>

    <div class="deux">
      <div class="carte anim-entree">
        <h3>Contrats</h3>
        <div class="stats-mini">
          <div><span class="v">{{ r.contrats.actifs }}</span><span class="l">Actifs</span></div>
          <div><span class="v">{{ r.contrats.expires }}</span><span class="l">Expirés</span></div>
          <div><span class="v">{{ r.contrats.resilies }}</span><span class="l">Résiliés</span></div>
        </div>
      </div>
      <div class="carte anim-entree">
        <h3>Stocks (période)</h3>
        <div class="stats-mini">
          <div><span class="v">{{ r.stocks.quantite_entrees }}</span><span class="l">Entrées</span></div>
          <div><span class="v">{{ r.stocks.quantite_sorties }}</span><span class="l">Sorties</span></div>
        </div>
      </div>
    </div>

    @if (r.repartition_par_filiale; as rep) {
      <div class="carte anim-entree">
        <h3>Répartition par filiale — montant validé</h3>
        <table class="tbl">
          <thead><tr><th>Filiale</th><th>Montant validé</th></tr></thead>
          <tbody>
            @for (f of rep; track f.filiale_id) {
              <tr><td>{{ f.filiale }}</td><td>{{ f.montant_valide | number:'1.2-2' }}</td></tr>
            }
          </tbody>
        </table>
      </div>
    }
  } @else if (chargement()) {
    <div class="carte anim-entree centre"><span class="spinner"></span></div>
  }
  `,
  styles: [`
    .entete { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1rem; }
    .sous-titre { color: var(--txt-2); font-size: .82rem; margin: .2rem 0 0; }
    .portee { color: var(--txt-2); font-size: .85rem; margin: 0 0 1rem; }

    .filtres { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: 1rem; }
    .champ { display: flex; flex-direction: column; gap: .3rem; }
    .champ label { font-size: .78rem; font-weight: 600; color: var(--txt-2); }
    .champ input, .champ select { border: 1px solid var(--bord); border-radius: 8px; padding: .5rem .7rem; font-size: .85rem; font-family: inherit; }

    .grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; margin-bottom: 1.4rem; }
    .kpi { background: #fff; border: 1px solid var(--bord); border-radius: var(--r);
      padding: 1rem; display: flex; align-items: center; gap: .8rem; transition: transform .15s, box-shadow .15s; }
    .kpi:hover { transform: translateY(-3px); box-shadow: var(--ombre-md); }
    .ic { width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center;
      justify-content: center; color: #fff; flex-shrink: 0; }
    .ic-navy { background: var(--navy); } .ic-bleu { background: var(--bleu); }
    .ic-orange { background: var(--accent); } .ic-vert { background: var(--vert); }
    .kpi .v { font-family: var(--police-titre); font-size: 1.5rem; font-weight: 700; color: var(--navy); line-height: 1; }
    .kpi .l { font-size: .78rem; color: var(--txt-2); margin-top: .25rem; }

    .deux { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
    @media (max-width: 800px) { .deux { grid-template-columns: 1fr; } }
    .stats-mini { display: flex; gap: 1.6rem; }
    .stats-mini > div { display: flex; flex-direction: column; }
    .stats-mini .v { font-family: var(--police-titre); font-size: 1.4rem; font-weight: 700; color: var(--navy); }
    .stats-mini .l { font-size: .78rem; color: var(--txt-2); }

    .tbl tfoot .total td { font-weight: 700; border-top: 2px solid var(--bord); }
    .centre { display: flex; justify-content: center; padding: 2.5rem; }
  `],
})
export class RapportsComponent implements OnInit {
  rapport = signal<RapportAdministratif | null>(null);
  filiales = signal<Filiale[]>([]);
  chargement = signal(false);
  exportEnCours = signal(false);
  erreur = signal('');

  dateDebut = premierJourDuMois();
  dateFin = aujourdHui();
  filialeId: number | null = null;

  constructor(private api: ApiService, public auth: AuthService) {}

  ngOnInit(): void {
    if (this.auth.aRole('ADMINISTRATEUR', 'DIRECTEUR')) {
      this.api.filiales().subscribe((p) => this.filiales.set(p.results));
    }
    this.charger();
  }

  private filtres() {
    return {
      date_debut: this.dateDebut,
      date_fin: this.dateFin,
      filiale: this.filialeId ?? undefined,
    };
  }

  charger(): void {
    this.erreur.set('');
    this.chargement.set(true);
    this.api.rapportAdministratif(this.filtres()).subscribe({
      next: (r) => { this.chargement.set(false); this.rapport.set(r); },
      error: () => { this.chargement.set(false); this.erreur.set('Impossible de charger le rapport.'); },
    });
  }

  exporter(): void {
    this.exportEnCours.set(true);
    this.api.exporterRapportAdministratif(this.filtres()).subscribe({
      next: (blob) => {
        this.exportEnCours.set(false);
        const url = window.URL.createObjectURL(blob);
        const lien = document.createElement('a');
        lien.href = url;
        lien.download = `rapport_administratif_${this.dateDebut}_${this.dateFin}.pdf`;
        lien.click();
        window.URL.revokeObjectURL(url);
      },
      error: () => {
        this.exportEnCours.set(false);
        this.erreur.set("Impossible d'exporter le rapport.");
      },
    });
  }
}
