import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { IconComponent } from '../../shared/icon.component';
import { ToastService } from '../../core/toast.service';
import { AuthService } from '../../core/auth.service';
import {
  CongesService, DemandeConge, MotifPermission, MouvementConge, SoldeConge,
} from '../../core/vie-interne.service';

/**
 * Congés et permissions exceptionnelles.
 *
 * Deux règles doivent se lire à l'écran sans explication :
 *
 * - le solde se cumule d'une année sur l'autre et n'est jamais perdu ;
 * - une permission (article 45 de la Convention Collective du Togo) ne se
 *   déduit pas du congé annuel, et chaque motif ouvre un nombre de jours
 *   fixe — que le formulaire affiche au moment du choix.
 */
@Component({
  selector: 'app-conges',
  imports: [CommonModule, FormsModule, IconComponent],
  template: `
  <div class="tete anim-entree">
    <div>
      <h1>Congés et permissions</h1>
      <p class="sous">Vos droits, vos demandes et leur suivi</p>
    </div>
    <button class="btn cta" (click)="ouvrirFormulaire()">
      <app-icon name="plus"/> Nouvelle demande
    </button>
  </div>

  @if (solde(); as s) {
    <div class="grille stagger">
      <div class="kpi">
        <div class="ic ic-vert"><app-icon name="checkCircle"/></div>
        <div>
          <div class="v">{{ nombre(s.disponible) }}</div>
          <div class="l">Jours disponibles</div>
        </div>
      </div>
      <div class="kpi">
        <div class="ic ic-bleu"><app-icon name="calendar"/></div>
        <div>
          <div class="v">{{ nombre(s.acquis_total) }}</div>
          <div class="l">Acquis depuis l'embauche</div>
        </div>
      </div>
      <div class="kpi">
        <div class="ic ic-navy"><app-icon name="clock"/></div>
        <div>
          <div class="v">{{ nombre(s.pris_total) }}</div>
          <div class="l">Jours pris</div>
        </div>
      </div>
      <div class="kpi">
        <div class="ic ic-orange"><app-icon name="clock"/></div>
        <div>
          <div class="v">{{ nombre(s.reserves) }}</div>
          <div class="l">En attente de validation</div>
        </div>
      </div>
    </div>

    <p class="note">
      <app-icon name="checkCircle" [size]="14"/>
      Vos jours non pris se reportent d'une année sur l'autre : ils ne sont
      jamais perdus. Acquisition de 2,5 jours par mois travaillé
      ({{ nombre(s.acquis) }} j acquis en {{ s.annee }}).
    </p>
  }

  <div class="onglets">
    <button [class.actif]="onglet() === 'mes'" (click)="onglet.set('mes')">
      Mes demandes
    </button>
    @if (aValider().length) {
      <button [class.actif]="onglet() === 'valider'" (click)="onglet.set('valider')">
        À valider <span class="pastille">{{ aValider().length }}</span>
      </button>
    }
    <button [class.actif]="onglet() === 'registre'" (click)="onglet.set('registre')">
      Mon registre
    </button>
  </div>

  @if (onglet() === 'mes') {
    <div class="carte anim-entree">
      @if (demandes().length) {
        <table class="tableau">
          <thead>
            <tr>
              <th>Type</th><th>Période</th><th>Jours</th>
              <th>Statut</th><th>Justificatif</th><th></th>
            </tr>
          </thead>
          <tbody>
            @for (d of demandes(); track d.id) {
              <tr>
                <td>
                  <strong>{{ d.type_libelle }}</strong>
                  @if (d.motif_permission_libelle) {
                    <div class="detail">{{ d.motif_permission_libelle }}</div>
                  }
                </td>
                <td>{{ d.date_debut | date: 'dd/MM/yyyy' }} → {{ d.date_fin | date: 'dd/MM/yyyy' }}</td>
                <td class="num">{{ d.jours_ouvres }}</td>
                <td><span class="etat" [class]="'etat-' + d.statut.toLowerCase()">{{ d.statut_libelle }}</span></td>
                <td>
                  @if (d.justificatif_attendu) {
                    @if (d.justificatif) {
                      <span class="ok"><app-icon name="checkCircle" [size]="14"/> Fourni</span>
                    } @else {
                      <label class="televerser" [class.retard]="d.justificatif_en_retard">
                        <input type="file" hidden (change)="envoyerJustificatif(d, $event)"/>
                        {{ d.justificatif_attendu }}
                        @if (d.justificatif_en_retard) { — en retard }
                      </label>
                    }
                  } @else { <span class="rien">—</span> }
                </td>
                <td>
                  @if (d.statut === 'EN_ATTENTE' || d.statut === 'VALIDEE') {
                    <button class="lien" (click)="annuler(d)">Annuler</button>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      } @else {
        <div class="vide">Aucune demande pour le moment.</div>
      }
    </div>
  }

  @if (onglet() === 'valider') {
    <div class="carte anim-entree">
      <table class="tableau">
        <thead>
          <tr><th>Salarié</th><th>Type</th><th>Période</th><th>Jours</th><th></th></tr>
        </thead>
        <tbody>
          @for (d of aValider(); track d.id) {
            <tr>
              <td>{{ d.utilisateur_nom }}</td>
              <td>
                {{ d.type_libelle }}
                @if (d.motif_permission_libelle) {
                  <div class="detail">{{ d.motif_permission_libelle }}</div>
                }
              </td>
              <td>{{ d.date_debut | date: 'dd/MM/yyyy' }} → {{ d.date_fin | date: 'dd/MM/yyyy' }}</td>
              <td class="num">{{ d.jours_ouvres }}</td>
              <td class="actions-ligne">
                <button class="btn petit vert" (click)="decider(d, true)">Valider</button>
                <button class="btn petit rouge" (click)="decider(d, false)">Refuser</button>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  }

  @if (onglet() === 'registre') {
    <div class="carte anim-entree">
      <p class="sous">
        Chaque jour crédité ou consommé laisse une ligne. Une correction
        s'écrit en ajoutant une écriture, jamais en modifiant l'historique.
      </p>
      @if (registre().length) {
        <table class="tableau">
          <thead><tr><th>Date</th><th>Nature</th><th>Jours</th><th>Motif</th></tr></thead>
          <tbody>
            @for (m of registre(); track m.id) {
              <tr>
                <td>{{ m.date_effet | date: 'dd/MM/yyyy' }}</td>
                <td>{{ m.type_libelle }}</td>
                <td class="num" [class.credit]="+m.jours > 0" [class.debit]="+m.jours < 0">
                  {{ +m.jours > 0 ? '+' : '' }}{{ nombre(m.jours) }}
                </td>
                <td class="detail">{{ m.motif }}</td>
              </tr>
            }
          </tbody>
        </table>
      } @else {
        <div class="vide">Aucun mouvement enregistré.</div>
      }
    </div>
  }

  @if (formulaireOuvert()) {
    <div class="voile" (click)="fermerFormulaire()">
      <div class="modale anim-entree" (click)="$event.stopPropagation()">
        <h3>Nouvelle demande</h3>

        <label>Type</label>
        <select [(ngModel)]="typeConge" (ngModelChange)="surChangementType()">
          <option value="ANNUEL">Congé annuel</option>
          <option value="PERMISSION">Permission exceptionnelle</option>
          <option value="MALADIE">Congé maladie</option>
          <option value="MATERNITE">Congé de maternité</option>
          <option value="SANS_SOLDE">Congé sans solde</option>
        </select>

        @if (typeConge === 'PERMISSION') {
          <label>Évènement</label>
          <select [(ngModel)]="motifPermission">
            <option value="">— choisir —</option>
            @for (m of bareme(); track m.code) {
              <option [value]="m.code">{{ m.libelle }} ({{ m.jours }} j)</option>
            }
          </select>

          @if (motifChoisi(); as m) {
            <p class="encart">
              <strong>{{ m.jours }} jour(s)</strong> accordés pour cet évènement.
              Justificatif : {{ m.justificatif }}, à fournir sous 8 jours.
              @if (m.anciennete_requise) {
                <br/>Six mois d'ancienneté requis.
              } @else {
                <br/>Aucune condition d'ancienneté.
              }
              <br/>Cette permission ne se déduit pas de votre congé annuel.
            </p>
          }

          <label>Date de l'évènement</label>
          <input type="date" [(ngModel)]="dateEvenement"/>
        }

        <div class="deux-champs">
          <div>
            <label>Du</label>
            <input type="date" [(ngModel)]="dateDebut"/>
          </div>
          <div>
            <label>Au</label>
            <input type="date" [(ngModel)]="dateFin"/>
          </div>
        </div>

        <label>Motif (facultatif)</label>
        <textarea rows="2" [(ngModel)]="motif"></textarea>

        <div class="pied">
          <button class="btn fantome" (click)="fermerFormulaire()">Annuler</button>
          <button class="btn cta" [disabled]="envoi()" (click)="soumettre()">
            {{ envoi() ? 'Envoi…' : 'Déposer la demande' }}
          </button>
        </div>
      </div>
    </div>
  }
  `,
  styles: [`
    .tete { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.4rem; }
    .sous { color: var(--txt-2); margin-top: -.3rem; font-size: .9rem; }
    .grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 1rem; }
    .kpi { background: #fff; border: 1px solid var(--bord); border-radius: var(--r);
      padding: 1.1rem 1.2rem; box-shadow: var(--ombre); display: flex; align-items: center; gap: 1rem; }
    .ic { width: 46px; height: 46px; border-radius: 12px; display: flex; align-items: center;
      justify-content: center; flex-shrink: 0; color: #fff; }
    .ic-navy { background: var(--navy); } .ic-bleu { background: var(--bleu); }
    .ic-orange { background: var(--accent); } .ic-vert { background: var(--vert); }
    .kpi .v { font-family: var(--police-titre); font-size: 1.7rem; font-weight: 700; color: var(--navy); line-height: 1; }
    .kpi .l { font-size: .8rem; color: var(--txt-2); margin-top: .25rem; }

    .note { display: flex; align-items: flex-start; gap: .5rem; margin: 1rem 0 1.4rem;
      padding: .75rem .9rem; background: #f0fdf4; border: 1px solid #bbf7d0;
      border-radius: 10px; font-size: .85rem; color: #166534; }
    .note app-icon { flex-shrink: 0; margin-top: .15rem; }

    .onglets { display: flex; gap: .4rem; margin-bottom: 1rem; border-bottom: 1px solid var(--bord); }
    .onglets button { background: none; border: none; padding: .7rem 1rem; cursor: pointer;
      font-size: .9rem; font-weight: 500; color: var(--txt-2); border-bottom: 2px solid transparent;
      transition: color var(--t), border-color var(--t); }
    .onglets button.actif { color: var(--navy); border-bottom-color: var(--bleu); }
    .pastille { background: var(--accent); color: #fff; border-radius: 999px;
      padding: .05rem .4rem; font-size: .7rem; margin-left: .3rem; }

    .tableau { width: 100%; border-collapse: collapse; font-size: .88rem; }
    .tableau th { text-align: left; padding: .6rem .5rem; color: var(--txt-2);
      font-weight: 600; font-size: .78rem; text-transform: uppercase; letter-spacing: .03em;
      border-bottom: 1px solid var(--bord); }
    .tableau td { padding: .7rem .5rem; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .tableau .num { font-weight: 700; color: var(--navy); }
    .detail { font-size: .78rem; color: var(--txt-2); margin-top: .15rem; }
    .credit { color: var(--vert); } .debit { color: #b42318; }

    .etat { padding: .2rem .55rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
    .etat-en_attente { background: #fef3c7; color: #92400e; }
    .etat-validee { background: #dcfce7; color: #166534; }
    .etat-refusee { background: #fee2e2; color: #991b1b; }
    .etat-annulee { background: #f1f5f9; color: #475569; }

    .televerser { cursor: pointer; color: var(--bleu); font-size: .8rem; text-decoration: underline; }
    .televerser.retard { color: #b42318; font-weight: 600; }
    .ok { color: var(--vert); font-size: .8rem; display: inline-flex; align-items: center; gap: .25rem; }
    .rien { color: var(--txt-2); }
    .lien { background: none; border: none; color: var(--bleu); cursor: pointer;
      font-size: .82rem; text-decoration: underline; padding: 0; }
    .actions-ligne { display: flex; gap: .4rem; }
    .btn.petit { padding: .3rem .7rem; font-size: .78rem; }
    .btn.vert { background: var(--vert); color: #fff; }
    .btn.rouge { background: #b42318; color: #fff; }
    .vide { text-align: center; color: var(--txt-2); padding: 2rem; font-size: .9rem; }

    .voile { position: fixed; inset: 0; background: rgba(15,23,42,.45); display: flex;
      align-items: center; justify-content: center; z-index: 60; padding: 1rem; }
    .modale { background: #fff; border-radius: var(--r); padding: 1.5rem; width: 100%;
      max-width: 480px; max-height: 90vh; overflow-y: auto; box-shadow: var(--ombre-md); }
    .modale h3 { margin: 0 0 1rem; color: var(--navy); }
    .modale label { display: block; font-size: .8rem; font-weight: 600; color: var(--txt-2);
      margin: .8rem 0 .3rem; }
    .modale select, .modale input, .modale textarea { width: 100%; padding: .6rem .7rem;
      border: 1px solid var(--bord); border-radius: 8px; font-size: .9rem; font-family: inherit; }
    .deux-champs { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }
    .encart { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
      padding: .7rem .8rem; font-size: .82rem; color: #1e40af; margin: .7rem 0 0; line-height: 1.5; }
    .pied { display: flex; justify-content: flex-end; gap: .6rem; margin-top: 1.4rem; }
    .btn.fantome { background: none; border: 1px solid var(--bord); color: var(--txt); }
  `],
})
export class CongesComponent implements OnInit {
  solde = signal<SoldeConge | null>(null);
  demandes = signal<DemandeConge[]>([]);
  aValider = signal<DemandeConge[]>([]);
  registre = signal<MouvementConge[]>([]);
  bareme = signal<MotifPermission[]>([]);

  onglet = signal<'mes' | 'valider' | 'registre'>('mes');
  formulaireOuvert = signal(false);
  envoi = signal(false);

  typeConge = 'ANNUEL';
  motifPermission = '';
  dateEvenement = '';
  dateDebut = '';
  dateFin = '';
  motif = '';

  /**
   * Motif sélectionné dans la liste déroulante.
   *
   * Méthode et non `computed()` : `motifPermission` est un champ lié par
   * `ngModel`, pas un signal. Un `computed` ne l'observerait pas et
   * l'encart rappelant le barème ne se mettrait jamais à jour.
   */
  motifChoisi(): MotifPermission | null {
    return this.bareme().find((m) => m.code === this.motifPermission) || null;
  }

  constructor(
    private conges: CongesService,
    private toast: ToastService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.recharger();
    this.conges.baremePermissions().subscribe((b) => this.bareme.set(b));
  }

  recharger(): void {
    this.conges.monSolde().subscribe((s) => this.solde.set(s));
    this.conges.mesDemandes().subscribe((r) => this.demandes.set(r.results ?? (r as any)));
    this.conges.aValider().subscribe((d) => this.aValider.set(d));
    this.conges.monRegistre().subscribe((m) => this.registre.set(m));
  }

  nombre(valeur: string | number): string {
    const n = typeof valeur === 'string' ? parseFloat(valeur) : valeur;
    if (Number.isNaN(n)) return '0';
    // 7.5 reste « 7,5 », 30.00 devient « 30 ».
    return n.toLocaleString('fr-FR', { maximumFractionDigits: 1 });
  }

  ouvrirFormulaire(): void {
    this.typeConge = 'ANNUEL';
    this.motifPermission = '';
    this.dateEvenement = '';
    this.dateDebut = '';
    this.dateFin = '';
    this.motif = '';
    this.formulaireOuvert.set(true);
  }

  fermerFormulaire(): void { this.formulaireOuvert.set(false); }

  surChangementType(): void {
    if (this.typeConge !== 'PERMISSION') {
      this.motifPermission = '';
      this.dateEvenement = '';
    }
  }

  soumettre(): void {
    if (!this.dateDebut || !this.dateFin) {
      this.toast.erreur('Renseignez les dates de début et de fin.');
      return;
    }

    this.envoi.set(true);
    this.conges.deposer({
      type_conge: this.typeConge,
      date_debut: this.dateDebut,
      date_fin: this.dateFin,
      motif: this.motif,
      motif_permission: this.motifPermission,
      date_evenement: this.dateEvenement || null,
    }).subscribe({
      next: () => {
        this.envoi.set(false);
        this.fermerFormulaire();
        this.toast.succes('Demande déposée.');
        this.recharger();
      },
      error: (e) => {
        this.envoi.set(false);
        this.toast.erreur(e?.error?.detail || 'La demande a été refusée.');
      },
    });
  }

  decider(d: DemandeConge, approuvee: boolean): void {
    this.conges.decider(d.id, approuvee).subscribe({
      next: () => {
        this.toast.succes(approuvee ? 'Demande validée.' : 'Demande refusée.');
        this.recharger();
      },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Action impossible.'),
    });
  }

  annuler(d: DemandeConge): void {
    this.conges.annuler(d.id).subscribe({
      next: () => { this.toast.succes('Demande annulée.'); this.recharger(); },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Annulation impossible.'),
    });
  }

  envoyerJustificatif(d: DemandeConge, evenement: Event): void {
    const entree = evenement.target as HTMLInputElement;
    const fichier = entree.files?.[0];
    if (!fichier) return;

    this.conges.deposerJustificatif(d.id, fichier).subscribe({
      next: () => { this.toast.succes('Justificatif enregistré.'); this.recharger(); },
      error: (e) => this.toast.erreur(e?.error?.detail || 'Dépôt impossible.'),
    });
  }
}
